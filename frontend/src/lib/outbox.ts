import { db } from "./db";

interface ItemLancamento {
  criterio_id: string;
  ocorrencias?: number;
  valor?: number;
  aplicado?: boolean;
}

interface EnfileirarCriarParams {
  fichaId: string;
  rodadaId: string;
  equipeId: string;
  tentativa: number;
  itens: ItemLancamento[];
  totalPreview: number;
  partidaId?: string;
}

interface EnfileirarConfirmarParams {
  lancamentoLocalId: string;
  revision: number;
  /**
   * So precisa ser informado quando nao existe um item CRIAR desta sessao
   * na fila (ex.: retomando um lancamento PENDENTE que ja veio do servidor
   * numa sessao anterior) — sem isso, o sync nao teria como achar o
   * lancamento_id pra confirmar.
   */
  lancamentoServidorId?: string;
}

export async function enfileirarCriarLancamento(
  params: EnfileirarCriarParams,
): Promise<{ lancamentoLocalId: string }> {
  const lancamentoLocalId = crypto.randomUUID();
  const clientOperationId = crypto.randomUUID();

  await db.lancamentoOutbox.put({
    clientOperationId,
    lancamentoLocalId,
    tipo: "CRIAR",
    payload: {
      ficha_id: params.fichaId,
      rodada_id: params.rodadaId,
      tentativa: params.tentativa,
      equipe_id: params.equipeId,
      ...(params.partidaId ? { partida_id: params.partidaId } : {}),
      client_operation_id: clientOperationId,
      itens: params.itens,
      totalPreview: params.totalPreview,
    },
    contexto: { rodadaId: params.rodadaId, equipeId: params.equipeId, tentativa: params.tentativa },
    revision: 1,
    updatedAtClient: new Date().toISOString(),
    status: "PENDENTE",
    tentativasEnvio: 0,
    criadoEm: Date.now(),
  });

  return { lancamentoLocalId };
}

export async function enfileirarConfirmarLancamento(
  params: EnfileirarConfirmarParams,
): Promise<void> {
  const criarItem = await db.lancamentoOutbox
    .where("lancamentoLocalId")
    .equals(params.lancamentoLocalId)
    .and((item) => item.tipo === "CRIAR")
    .first();

  const clientOperationId = crypto.randomUUID();

  await db.lancamentoOutbox.put({
    clientOperationId,
    lancamentoLocalId: params.lancamentoLocalId,
    lancamentoServidorId: params.lancamentoServidorId ?? criarItem?.lancamentoServidorId,
    tipo: "CONFIRMAR",
    dependeDe: criarItem?.clientOperationId,
    payload: {},
    contexto: criarItem?.contexto ?? { rodadaId: "", equipeId: "", tentativa: 0 },
    revision: params.revision,
    updatedAtClient: new Date().toISOString(),
    status: "PENDENTE",
    tentativasEnvio: 0,
    criadoEm: Date.now(),
  });
}
