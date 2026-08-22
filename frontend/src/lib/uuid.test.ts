import { describe, expect, it } from "vitest";

import { randomUUID } from "./uuid";

const REGEX_UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe("randomUUID", () => {
  it("gera uma string no formato UUID v4", () => {
    expect(randomUUID()).toMatch(REGEX_UUID_V4);
  });

  it("gera valores diferentes a cada chamada", () => {
    const valores = Array.from({ length: 20 }, () => randomUUID());

    expect(new Set(valores).size).toBe(valores.length);
  });
});
