import type { LancamentoOutboxItem } from "./db";

export type EstadoSincronizacao = "pendente" | "enviando" | "sincronizado" | "conflito" | "erro";

export interface LancamentoAtivoView {
  id: string;
  lancamentoLocalId: string;
  total: number;
  status: "PENDENTE" | "CONFIRMADO";
  estadoSincronizacao: EstadoSincronizacao;
  conflito?: { mensagem: string; codigo: string };
}

function estadoDoItem(item: LancamentoOutboxItem): EstadoSincronizacao {
  if (item.status === "ENVIANDO") return "enviando";
  if (item.status === "ERRO") return "erro";
  return "pendente";
}

export function derivarLancamentoAtivo(params: {
  itensDaFila: LancamentoOutboxItem[];
}): LancamentoAtivoView | null {
  const { itensDaFila } = params;

  const conflito = itensDaFila.find((item) => item.status === "CONFLITO");
  if (conflito) {
    return {
      id: conflito.lancamentoLocalId,
      lancamentoLocalId: conflito.lancamentoLocalId,
      total: 0,
      status: "PENDENTE",
      estadoSincronizacao: "conflito",
      conflito: {
        mensagem: conflito.ultimoErro?.mensagem ?? "Conflito ao sincronizar o lançamento.",
        codigo: conflito.ultimoErro?.codigo ?? "CONFLITO",
      },
    };
  }

  const criar = itensDaFila.find((item) => item.tipo === "CRIAR");
  if (!criar) return null;

  if (criar.status !== "SINCRONIZADO") {
    const totalPreview = (criar.payload.totalPreview as number | undefined) ?? 0;
    return {
      id: criar.lancamentoLocalId,
      lancamentoLocalId: criar.lancamentoLocalId,
      total: totalPreview,
      status: "PENDENTE",
      estadoSincronizacao: estadoDoItem(criar),
    };
  }

  // Uma vez que o CRIAR sincronizou, o total/status de referencia passam a
  // ser o que o servidor respondeu naquele momento (guardado localmente em
  // resultadoServidor) - a tela nao depende do refetch da listagem da
  // rodada pra mostrar isso corretamente, evitando um instante em que o
  // card some so porque o GET ainda nao foi invalidado/refeito.
  const idServidor = criar.lancamentoServidorId ?? criar.lancamentoLocalId;
  const totalServidor =
    criar.resultadoServidor?.total ?? (criar.payload.totalPreview as number | undefined) ?? 0;

  const confirmar = itensDaFila.find((item) => item.tipo === "CONFIRMAR");
  if (confirmar && confirmar.status !== "SINCRONIZADO") {
    return {
      id: idServidor,
      lancamentoLocalId: criar.lancamentoLocalId,
      total: totalServidor,
      status: "PENDENTE",
      estadoSincronizacao: estadoDoItem(confirmar),
    };
  }

  const confirmado = !!confirmar && confirmar.status === "SINCRONIZADO";
  return {
    id: idServidor,
    lancamentoLocalId: criar.lancamentoLocalId,
    total: confirmado ? (confirmar?.resultadoServidor?.total ?? totalServidor) : totalServidor,
    status: confirmado ? "CONFIRMADO" : "PENDENTE",
    estadoSincronizacao: "sincronizado",
  };
}
