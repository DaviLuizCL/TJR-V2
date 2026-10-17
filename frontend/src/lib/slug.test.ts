import { describe, expect, it } from "vitest";

import { slug } from "./slug";

describe("slug", () => {
  it.each([
    ["Dança", "danca"],
    ["Resgate de Alto Risco", "resgate-de-alto-risco"],
    ["Viagem ao Centro da Terra", "viagem-ao-centro-da-terra"],
    ["Sumô RC 1,5 kg", "sumo-rc-1-5-kg"],
    ["  Resgate  no Plano ", "resgate-no-plano"],
  ])("%s vira %s", (nome, esperado) => {
    expect(slug(nome)).toBe(esperado);
  });
});
