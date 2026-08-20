import Dexie, { type EntityTable } from "dexie";

export type LancamentoOutboxTipo = "CRIAR" | "CONFIRMAR";

export type LancamentoOutboxStatus =
  | "PENDENTE"
  | "ENVIANDO"
  | "SINCRONIZADO"
  | "CONFLITO"
  | "ERRO";

export interface LancamentoOutboxErro {
  codigo: string;
  mensagem: string;
  detalhes: Record<string, unknown>;
  httpStatus: number;
}

export interface LancamentoOutboxItem {
  clientOperationId: string;
  lancamentoLocalId: string;
  lancamentoServidorId?: string;
  tipo: LancamentoOutboxTipo;
  dependeDe?: string;
  payload: Record<string, unknown>;
  contexto: { rodadaId: string; equipeId: string; tentativa: number };
  revision: number;
  updatedAtClient: string;
  status: LancamentoOutboxStatus;
  tentativasEnvio: number;
  ultimoErro?: LancamentoOutboxErro;
  /**
   * Snapshot do que o servidor respondeu quando este item sincronizou.
   * Guardado localmente pra tela nao depender do refetch da listagem de
   * lancamentos da rodada (que pode nao ter refletido a mudanca ainda) pra
   * mostrar o total/status corretos logo apos sincronizar.
   */
  resultadoServidor?: { status: string; total: number };
  criadoEm: number;
}

const db = new Dexie("tjr-outbox") as Dexie & {
  lancamentoOutbox: EntityTable<LancamentoOutboxItem, "clientOperationId">;
};

db.version(1).stores({
  lancamentoOutbox:
    "clientOperationId, lancamentoLocalId, status, criadoEm, [contexto.rodadaId+contexto.equipeId+contexto.tentativa]",
});

export { db };
