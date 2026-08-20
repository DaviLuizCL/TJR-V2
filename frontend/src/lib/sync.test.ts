import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { db, type LancamentoOutboxItem } from "./db";
import { enfileirarCriarLancamento } from "./outbox";
import { sincronizar } from "./sync";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: { ...actual.api, POST: vi.fn(), GET: vi.fn() },
  };
});

beforeEach(async () => {
  await db.lancamentoOutbox.clear();
  vi.clearAllMocks();
});

async function itemUnico(): Promise<LancamentoOutboxItem> {
  const itens = await db.lancamentoOutbox.toArray();
  return itens[0];
}

describe("sincronizar", () => {
  it("drena um item PENDENTE chamando a API uma vez com o client_operation_id do item e marca SINCRONIZADO", async () => {
    await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 10,
    });
    const antes = await itemUnico();

    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "lanc-servidor-1" },
      error: undefined,
      response: { status: 201 },
    } as never);

    await sincronizar();

    expect(api.POST).toHaveBeenCalledTimes(1);
    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/lancamentos",
      expect.objectContaining({
        body: expect.objectContaining({ client_operation_id: antes.clientOperationId }),
      }),
    );

    const depois = await itemUnico();
    expect(depois.status).toBe("SINCRONIZADO");
    expect(depois.lancamentoServidorId).toBe("lanc-servidor-1");
  });

  it("reentrancia nao reenvia item ja sincronizado", async () => {
    await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 10,
    });

    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "lanc-servidor-1" },
      error: undefined,
      response: { status: 201 },
    } as never);

    await sincronizar();
    await sincronizar();

    expect(api.POST).toHaveBeenCalledTimes(1);
  });

  it("falha de rede volta o item pra PENDENTE e sincronizar() resolve sem travar", async () => {
    await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 10,
    });

    vi.mocked(api.POST).mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(sincronizar()).resolves.toBeUndefined();

    const depois = await itemUnico();
    expect(depois.status).toBe("PENDENTE");
    expect(depois.tentativasEnvio).toBe(1);
  });

  it("conflito 409 LANCAMENTO_JA_EXISTE marca CONFLITO e nao reenvia automaticamente", async () => {
    await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 10,
    });

    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: {
        erro: {
          codigo: "LANCAMENTO_JA_EXISTE",
          mensagem: "Ja existe lancamento para essa equipe/tentativa.",
          detalhes: { lancamento_id: "lanc-de-outro" },
        },
      },
      response: { status: 409 },
    } as never);

    await sincronizar();

    const depois = await itemUnico();
    expect(depois.status).toBe("CONFLITO");
    expect(depois.ultimoErro?.codigo).toBe("LANCAMENTO_JA_EXISTE");

    await sincronizar();
    expect(api.POST).toHaveBeenCalledTimes(1);
  });
});
