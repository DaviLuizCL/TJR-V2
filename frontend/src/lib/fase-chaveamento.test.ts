import { describe, expect, it } from "vitest";

import { calcularTotalRodadasPorNivel, nomeFase } from "./fase-chaveamento";

describe("nomeFase", () => {
  it("bracket de 2 equipes: rodada 1 e a final", () => {
    expect(nomeFase(1, 1)).toEqual({
      nome: "Final",
      classes: "bg-amber-100 text-amber-800 border border-amber-300",
    });
  });

  it("bracket de 4 equipes: rodada 1 e semifinal, rodada 2 e final", () => {
    expect(nomeFase(1, 2)?.nome).toBe("Semifinal");
    expect(nomeFase(2, 2)?.nome).toBe("Final");
  });

  it("bracket de 8 equipes: quartas, semifinal, final em ordem", () => {
    expect(nomeFase(1, 3)?.nome).toBe("Quartas de Final");
    expect(nomeFase(2, 3)?.nome).toBe("Semifinal");
    expect(nomeFase(3, 3)?.nome).toBe("Final");
  });

  it("bracket de 16 equipes: oitavas na rodada 1", () => {
    expect(nomeFase(1, 4)?.nome).toBe("Oitavas de Final");
  });

  it("bracket maior que 16 equipes nao tem nome de fase pra rodada 1 (fallback pro chamador)", () => {
    expect(nomeFase(1, 5)).toBeNull();
  });

  it("retorna null quando nao sabe o total de rodadas do nivel", () => {
    expect(nomeFase(1, undefined)).toBeNull();
    expect(nomeFase(1, 0)).toBeNull();
  });
});

describe("calcularTotalRodadasPorNivel", () => {
  it("conta as equipes unicas da rodada 1 por nivel e calcula rodadas necessarias", () => {
    const partidas = [
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "b" },
      { nivel: 1, equipe_a_id: "c", equipe_b_id: "d" },
      { nivel: 2, equipe_a_id: "e", equipe_b_id: "f" },
    ];

    const resultado = calcularTotalRodadasPorNivel(partidas);

    expect(resultado.get(1)).toBe(2); // 4 equipes -> 2 rodadas
    expect(resultado.get(2)).toBe(1); // 2 equipes -> 1 rodada
  });

  it("ignora partidas sem nivel e conta bye (equipe_b_id nulo) como 1 equipe so", () => {
    const partidas = [
      { nivel: null, equipe_a_id: "x", equipe_b_id: "y" },
      { nivel: 3, equipe_a_id: "a", equipe_b_id: null },
    ];

    const resultado = calcularTotalRodadasPorNivel(partidas);

    expect(resultado.has(null as unknown as number)).toBe(false);
    expect(resultado.get(3)).toBe(0);
  });
});
