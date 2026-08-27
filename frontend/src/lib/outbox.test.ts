import { beforeEach, describe, expect, it, vi } from "vitest";

import { db } from "./db";
import { enfileirarConfirmarLancamento, enfileirarCriarLancamento } from "./outbox";

beforeEach(async () => {
  await db.lancamentoOutbox.clear();
});

describe("outbox", () => {
  it("enfileirarCriarLancamento resolve sem chamar rede e grava item PENDENTE", async () => {
    const { lancamentoLocalId } = await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [{ criterio_id: "crit-1", ocorrencias: 1 }],
      totalPreview: 10,
    });

    const itens = await db.lancamentoOutbox.toArray();
    expect(itens).toHaveLength(1);
    expect(itens[0].tipo).toBe("CRIAR");
    expect(itens[0].status).toBe("PENDENTE");
    expect(itens[0].lancamentoLocalId).toBe(lancamentoLocalId);
    expect(itens[0].contexto).toEqual({ rodadaId: "rod-1", equipeId: "eq-1", tentativa: 1 });
  });

  it("inclui tempo_gasto_seg no payload quando informado", async () => {
    await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 0,
      tempoGastoSeg: 87,
    });

    const item = (await db.lancamentoOutbox.toArray())[0];
    expect(item.payload.tempo_gasto_seg).toBe(87);
  });

  it("nao inclui tempo_gasto_seg no payload quando nao informado", async () => {
    await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 0,
    });

    const item = (await db.lancamentoOutbox.toArray())[0];
    expect(item.payload.tempo_gasto_seg).toBeUndefined();
  });

  it("gera um client_operation_id fixo, nao reaproveita a cada chamada", async () => {
    const primeira = await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 0,
    });
    const segunda = await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-2",
      tentativa: 1,
      itens: [],
      totalPreview: 0,
    });

    expect(primeira.lancamentoLocalId).not.toBe(segunda.lancamentoLocalId);
    const itens = await db.lancamentoOutbox.toArray();
    const idsUnicos = new Set(itens.map((i) => i.clientOperationId));
    expect(idsUnicos.size).toBe(itens.length);
  });

  it("enfileirarConfirmarLancamento grava item CONFIRMAR referenciando o CRIAR", async () => {
    const { lancamentoLocalId } = await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 0,
    });
    const criarItem = (await db.lancamentoOutbox.toArray())[0];

    await enfileirarConfirmarLancamento({ lancamentoLocalId, revision: 1 });

    const itens = await db.lancamentoOutbox.toArray();
    const confirmar = itens.find((i) => i.tipo === "CONFIRMAR");
    expect(confirmar).toBeDefined();
    expect(confirmar?.dependeDe).toBe(criarItem.clientOperationId);
    expect(confirmar?.status).toBe("PENDENTE");
  });

  it("nao chama api nenhuma vez ao enfileirar", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    await enfileirarCriarLancamento({
      fichaId: "ficha-1",
      rodadaId: "rod-1",
      equipeId: "eq-1",
      tentativa: 1,
      itens: [],
      totalPreview: 0,
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
