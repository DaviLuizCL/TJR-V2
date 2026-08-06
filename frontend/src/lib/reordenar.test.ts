import { describe, expect, it } from "vitest";

import { reordenarPorArrasto } from "./reordenar";

interface ItemComOrdem {
  id: string;
  ordem: number;
}

function item(id: string, ordem: number): ItemComOrdem {
  return { id, ordem };
}

describe("reordenarPorArrasto", () => {
  it("move o item arrastado para a posicao do item soltado, renumerando ordem a partir de 1", () => {
    const itens = [item("a", 1), item("b", 2), item("c", 3)];

    const resultado = reordenarPorArrasto(itens, "a", "c");

    expect(resultado.map((i) => i.id)).toEqual(["b", "c", "a"]);
    expect(resultado.map((i) => i.ordem)).toEqual([1, 2, 3]);
  });

  it("nao muda nada se o item for solto sobre ele mesmo", () => {
    const itens = [item("a", 1), item("b", 2)];

    const resultado = reordenarPorArrasto(itens, "a", "a");

    expect(resultado.map((i) => i.id)).toEqual(["a", "b"]);
  });

  it("respeita a ordem original mesmo se o array de entrada nao estiver ordenado", () => {
    const itens = [item("c", 3), item("a", 1), item("b", 2)];

    const resultado = reordenarPorArrasto(itens, "b", "a");

    expect(resultado.map((i) => i.id)).toEqual(["b", "a", "c"]);
  });
});
