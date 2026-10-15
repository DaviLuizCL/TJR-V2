import { describe, expect, it } from "vitest";

import { iconeModalidade } from "./modalidade-icone";

describe("iconeModalidade", () => {
  it.each([
    ["Sumô", "🥋"],
    ["Sumô RC 1,5 kg", "🥋"],
    ["Cabo de Guerra", "🪢"],
    ["Corrida de Carros Autônomos", "🏎️"],
    ["Dança", "💃"],
    ["Resgate no Plano", "🚑"],
    ["Resgate de Alto Risco", "🧗"],
    ["Viagem ao Centro da Terra", "🌋"],
  ])("da um icone conhecido pra %s", (nome, icone) => {
    expect(iconeModalidade(nome)).toBe(icone);
  });

  it("cai no robo pra modalidade que nao conhece", () => {
    expect(iconeModalidade("Modalidade Nova")).toBe("🤖");
  });
});
