import { beforeEach, describe, expect, it } from "vitest";

import { db } from "./db";

beforeEach(async () => {
  await db.lancamentoOutbox.clear();
});

describe("db (outbox local)", () => {
  it("grava e le um item da fila de lancamentos", async () => {
    await db.lancamentoOutbox.put({
      clientOperationId: "op-1",
      lancamentoLocalId: "local-1",
      tipo: "CRIAR",
      payload: { foo: "bar" },
      contexto: { rodadaId: "rod-1", equipeId: "eq-1", tentativa: 1 },
      revision: 1,
      updatedAtClient: new Date().toISOString(),
      status: "PENDENTE",
      tentativasEnvio: 0,
      criadoEm: Date.now(),
    });

    const item = await db.lancamentoOutbox.get("op-1");

    expect(item).toBeDefined();
    expect(item?.lancamentoLocalId).toBe("local-1");
    expect(item?.status).toBe("PENDENTE");
  });

  it("consegue buscar itens pelo contexto rodada+equipe+tentativa", async () => {
    await db.lancamentoOutbox.put({
      clientOperationId: "op-2",
      lancamentoLocalId: "local-2",
      tipo: "CRIAR",
      payload: {},
      contexto: { rodadaId: "rod-1", equipeId: "eq-2", tentativa: 1 },
      revision: 1,
      updatedAtClient: new Date().toISOString(),
      status: "PENDENTE",
      tentativasEnvio: 0,
      criadoEm: Date.now(),
    });

    const itens = await db.lancamentoOutbox
      .where("[contexto.rodadaId+contexto.equipeId+contexto.tentativa]")
      .equals(["rod-1", "eq-2", 1])
      .toArray();

    expect(itens).toHaveLength(1);
    expect(itens[0].clientOperationId).toBe("op-2");
  });
});
