import { api, extrairErro } from "../api/client";
import { db, type LancamentoOutboxItem } from "./db";
import { queryClient } from "./query-client";

let sincronizando = false;
let precisaNovaPassada = false;

/**
 * So para teste: um mock de rede que nunca resolve (simulando API fora do
 * ar) deixa `sincronizando` travado em `true` pro resto do processo, ja que
 * a promise dentro do processamento nunca retorna. Sem resetar entre
 * testes, isso vaza pro teste seguinte e faz sincronizar() virar no-op.
 */
export function _resetarSincronizacaoParaTeste(): void {
  sincronizando = false;
  precisaNovaPassada = false;
}

const CODIGOS_CONFLITO = new Set(["LANCAMENTO_JA_EXISTE", "LANCAMENTO_NAO_PENDENTE"]);

type ResultadoProcessamento = "ok" | "rede" | "parado" | "aguardando";

async function marcarEnviando(item: LancamentoOutboxItem): Promise<void> {
  await db.lancamentoOutbox.update(item.clientOperationId, { status: "ENVIANDO" });
}

async function marcarSincronizado(
  item: LancamentoOutboxItem,
  extra?: {
    lancamentoServidorId?: string;
    resultadoServidor?: { status: string; total: number };
  },
): Promise<void> {
  await db.lancamentoOutbox.update(item.clientOperationId, {
    status: "SINCRONIZADO",
    ...(extra?.lancamentoServidorId ? { lancamentoServidorId: extra.lancamentoServidorId } : {}),
    ...(extra?.resultadoServidor ? { resultadoServidor: extra.resultadoServidor } : {}),
  });
}

function resultadoServidorDe(data: unknown): { status: string; total: number } | undefined {
  const resposta = data as { status?: string; total?: number } | undefined;
  if (resposta?.status === undefined || resposta?.total === undefined) return undefined;
  return { status: resposta.status, total: resposta.total };
}

async function marcarFalhaDeRede(item: LancamentoOutboxItem): Promise<void> {
  await db.lancamentoOutbox.update(item.clientOperationId, {
    status: "PENDENTE",
    tentativasEnvio: item.tentativasEnvio + 1,
  });
}

async function marcarFalhaDeNegocio(
  item: LancamentoOutboxItem,
  status: "CONFLITO" | "ERRO",
  httpStatus: number,
  erro: { codigo: string; mensagem: string; detalhes: Record<string, unknown> },
): Promise<void> {
  await db.lancamentoOutbox.update(item.clientOperationId, {
    status,
    ultimoErro: { ...erro, httpStatus },
  });
}

async function invalidarQueries(item: LancamentoOutboxItem): Promise<void> {
  await queryClient.invalidateQueries({
    queryKey: ["lancamentos-da-rodada", item.contexto.rodadaId],
  });
  await queryClient.invalidateQueries({
    queryKey: ["partidas-da-rodada", item.contexto.rodadaId],
  });
}

async function tratarResposta(
  item: LancamentoOutboxItem,
  data: unknown,
  error: unknown,
  response: Response | undefined,
  onSucesso: (data: unknown) => Promise<void>,
): Promise<ResultadoProcessamento> {
  // A falha de rede real (fetch rejeitado) ja foi tratada no catch do
  // chamador. Aqui so sobra a resposta normal do servidor: sucesso quando
  // nao ha erro de negocio, falha caso contrario. `response` pode nao vir
  // preenchido (ex.: alguns mocks de teste so simulam data/error) - por
  // isso so e usado de forma otimista pra classificar 409 como conflito,
  // nunca pra decidir sucesso/fracasso.
  if (!error && data !== undefined) {
    await onSucesso(data);
    await invalidarQueries(item);
    return "ok";
  }

  const erroApi = extrairErro(error);
  const status =
    response?.status === 409 || CODIGOS_CONFLITO.has(erroApi.codigo) ? "CONFLITO" : "ERRO";
  await marcarFalhaDeNegocio(item, status, response?.status ?? 0, erroApi);
  return "parado";
}

async function processarCriar(item: LancamentoOutboxItem): Promise<ResultadoProcessamento> {
  await marcarEnviando(item);

  const body: Record<string, unknown> = { ...item.payload };
  delete body.totalPreview;

  try {
    const { data, error, response } = await api.POST("/api/v1/lancamentos", {
      body: body as never,
    });
    return await tratarResposta(item, data, error, response, async (d) => {
      const lancamentoServidorId = (d as { id?: string } | undefined)?.id;
      await marcarSincronizado(item, {
        lancamentoServidorId,
        resultadoServidor: resultadoServidorDe(d),
      });
    });
  } catch {
    await marcarFalhaDeRede(item);
    return "rede";
  }
}

async function processarConfirmar(item: LancamentoOutboxItem): Promise<ResultadoProcessamento> {
  const criarItem = item.dependeDe ? await db.lancamentoOutbox.get(item.dependeDe) : undefined;
  const lancamentoId = item.lancamentoServidorId ?? criarItem?.lancamentoServidorId;
  if (!lancamentoId) {
    return "aguardando";
  }

  await marcarEnviando(item);

  try {
    const { data, error, response } = await api.POST(
      "/api/v1/lancamentos/{lancamento_id}/confirmar",
      { params: { path: { lancamento_id: lancamentoId } } },
    );
    return await tratarResposta(item, data, error, response, async (d) => {
      await marcarSincronizado(item, { resultadoServidor: resultadoServidorDe(d) });
    });
  } catch {
    await marcarFalhaDeRede(item);
    return "rede";
  }
}

export async function sincronizar(): Promise<void> {
  // Se ja existe uma drenagem em andamento, nao processa aqui: so sinaliza
  // que precisa de mais uma passada ao final da que esta rodando. Sem isso,
  // um item enfileirado (ex.: confirmar clicado logo apos registrar, antes
  // do POST de criar terminar) ficaria PENDENTE parado sem ninguem pra
  // drenar - a chamada reentrante seria descartada em silencio.
  if (sincronizando) {
    precisaNovaPassada = true;
    return;
  }

  sincronizando = true;
  try {
    do {
      precisaNovaPassada = false;
      const pendentes = await db.lancamentoOutbox
        .where("status")
        .equals("PENDENTE")
        .sortBy("criadoEm");

      for (const item of pendentes) {
        const atual = await db.lancamentoOutbox.get(item.clientOperationId);
        if (!atual || atual.status !== "PENDENTE") continue;

        const resultado =
          atual.tipo === "CRIAR" ? await processarCriar(atual) : await processarConfirmar(atual);

        if (resultado === "rede") return;
      }
    } while (precisaNovaPassada);
  } finally {
    sincronizando = false;
  }
}
