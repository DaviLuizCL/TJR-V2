import { describe, expect, it } from "vitest";

import type { LancamentoOutboxItem } from "./db";
import { derivarLancamentoAtivo } from "./lancamento-outbox-view";

function itemCriar(overrides: Partial<LancamentoOutboxItem> = {}): LancamentoOutboxItem {
  return {
    clientOperationId: "op-criar",
    lancamentoLocalId: "local-1",
    tipo: "CRIAR",
    payload: { totalPreview: 30 },
    contexto: { rodadaId: "rod-1", equipeId: "eq-1", tentativa: 1 },
    revision: 1,
    updatedAtClient: new Date().toISOString(),
    status: "PENDENTE",
    tentativasEnvio: 0,
    criadoEm: Date.now(),
    ...overrides,
  };
}

function itemConfirmar(overrides: Partial<LancamentoOutboxItem> = {}): LancamentoOutboxItem {
  return {
    clientOperationId: "op-confirmar",
    lancamentoLocalId: "local-1",
    tipo: "CONFIRMAR",
    dependeDe: "op-criar",
    payload: {},
    contexto: { rodadaId: "rod-1", equipeId: "eq-1", tentativa: 1 },
    revision: 1,
    updatedAtClient: new Date().toISOString(),
    status: "PENDENTE",
    tentativasEnvio: 0,
    criadoEm: Date.now(),
    ...overrides,
  };
}

describe("derivarLancamentoAtivo", () => {
  it("retorna null quando nao ha nada na fila", () => {
    const resultado = derivarLancamentoAtivo({ itensDaFila: [] });
    expect(resultado).toBeNull();
  });

  it("item CRIAR pendente mostra estado pendente com o total do preview", () => {
    const resultado = derivarLancamentoAtivo({
      itensDaFila: [itemCriar({ status: "PENDENTE" })],
    });

    expect(resultado?.estadoSincronizacao).toBe("pendente");
    expect(resultado?.total).toBe(30);
    expect(resultado?.status).toBe("PENDENTE");
  });

  it("item CRIAR enviando mostra estado enviando", () => {
    const resultado = derivarLancamentoAtivo({
      itensDaFila: [itemCriar({ status: "ENVIANDO" })],
    });

    expect(resultado?.estadoSincronizacao).toBe("enviando");
  });

  it("CRIAR sincronizado sem CONFIRMAR pendente usa o total/status que o servidor respondeu e marca sincronizado", () => {
    const resultado = derivarLancamentoAtivo({
      itensDaFila: [
        itemCriar({
          status: "SINCRONIZADO",
          lancamentoServidorId: "lanc-servidor-1",
          resultadoServidor: { status: "PENDENTE", total: 30 },
        }),
      ],
    });

    expect(resultado?.estadoSincronizacao).toBe("sincronizado");
    expect(resultado?.id).toBe("lanc-servidor-1");
    expect(resultado?.total).toBe(30);
    expect(resultado?.status).toBe("PENDENTE");
  });

  it("CRIAR sincronizado com CONFIRMAR ainda pendente mostra confirmacao pendente de envio", () => {
    const resultado = derivarLancamentoAtivo({
      itensDaFila: [
        itemCriar({
          status: "SINCRONIZADO",
          lancamentoServidorId: "lanc-servidor-1",
          resultadoServidor: { status: "PENDENTE", total: 30 },
        }),
        itemConfirmar({ status: "PENDENTE" }),
      ],
    });

    expect(resultado?.estadoSincronizacao).toBe("pendente");
    expect(resultado?.status).toBe("PENDENTE");
    expect(resultado?.total).toBe(30);
  });

  it("CRIAR e CONFIRMAR sincronizados mostram status CONFIRMADO", () => {
    const resultado = derivarLancamentoAtivo({
      itensDaFila: [
        itemCriar({
          status: "SINCRONIZADO",
          lancamentoServidorId: "lanc-servidor-1",
          resultadoServidor: { status: "PENDENTE", total: 30 },
        }),
        itemConfirmar({
          status: "SINCRONIZADO",
          resultadoServidor: { status: "CONFIRMADO", total: 30 },
        }),
      ],
    });

    expect(resultado?.estadoSincronizacao).toBe("sincronizado");
    expect(resultado?.status).toBe("CONFIRMADO");
    expect(resultado?.total).toBe(30);
  });

  it("item em CONFLITO nunca mistura com o card normal de sucesso", () => {
    const resultado = derivarLancamentoAtivo({
      itensDaFila: [
        itemCriar({
          status: "CONFLITO",
          ultimoErro: {
            codigo: "LANCAMENTO_JA_EXISTE",
            mensagem: "Ja existe lancamento para essa equipe/tentativa.",
            detalhes: {},
            httpStatus: 409,
          },
        }),
      ],
    });

    expect(resultado?.estadoSincronizacao).toBe("conflito");
    expect(resultado?.conflito?.codigo).toBe("LANCAMENTO_JA_EXISTE");
  });
});
