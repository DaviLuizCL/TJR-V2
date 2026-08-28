import { describe, expect, it } from "vitest";

import {
  calcularTotalRodadasPorNivel,
  nomeFase,
  primeiraRodadaMataMataPorNivel,
} from "./fase-chaveamento";

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
  it("conta as equipes unicas da 1a rodada MATA_MATA por nivel e calcula rodadas necessarias", () => {
    const partidas = [
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "b", formato_chaveamento: "MATA_MATA", numero: 1 },
      { nivel: 1, equipe_a_id: "c", equipe_b_id: "d", formato_chaveamento: "MATA_MATA", numero: 1 },
      { nivel: 2, equipe_a_id: "e", equipe_b_id: "f", formato_chaveamento: "MATA_MATA", numero: 1 },
    ];

    const resultado = calcularTotalRodadasPorNivel(partidas);

    expect(resultado.get(1)).toBe(2); // 4 equipes -> 2 rodadas
    expect(resultado.get(2)).toBe(1); // 2 equipes -> 1 rodada
  });

  it("ignora partidas sem nivel e conta bye (equipe_b_id nulo) como 1 equipe so", () => {
    const partidas = [
      {
        nivel: null,
        equipe_a_id: "x",
        equipe_b_id: "y",
        formato_chaveamento: "MATA_MATA",
        numero: 1,
      },
      { nivel: 3, equipe_a_id: "a", equipe_b_id: null, formato_chaveamento: "MATA_MATA", numero: 1 },
    ];

    const resultado = calcularTotalRodadasPorNivel(partidas);

    expect(resultado.has(null as unknown as number)).toBe(false);
    expect(resultado.get(3)).toBe(0);
  });

  it("ignora partidas de fase de grupos (TODOS_CONTRA_TODOS) ao calcular o bracket", () => {
    // Nivel que passou por fase de grupos: rodadas 1 e 2 sao TODOS_CONTRA_TODOS
    // (chave), o mata-mata so comeca na rodada 3 -- o total de rodadas do
    // bracket tem que vir das equipes da rodada 3, nao da 1.
    const partidas = [
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "b", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
      { nivel: 1, equipe_a_id: "c", equipe_b_id: "d", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "c", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 2 },
      { nivel: 1, equipe_a_id: "b", equipe_b_id: "e", formato_chaveamento: "MATA_MATA", numero: 3 },
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "d", formato_chaveamento: "MATA_MATA", numero: 3 },
    ];

    const resultado = calcularTotalRodadasPorNivel(partidas);

    // 4 equipes na 1a rodada MATA_MATA (numero 3) -> 2 rodadas ate a final,
    // mesmo com 5 equipes distintas aparecendo no total (fase de grupos).
    expect(resultado.get(1)).toBe(2);
  });

  it("nivel que so tem fase de grupos (sem mata-mata ainda) nao entra no resultado", () => {
    const partidas = [
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "b", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
    ];

    const resultado = calcularTotalRodadasPorNivel(partidas);

    expect(resultado.has(1)).toBe(false);
  });
});

describe("primeiraRodadaMataMataPorNivel", () => {
  it("acha, por nivel, o menor numero de rodada cujas partidas sao MATA_MATA", () => {
    const partidas = [
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "b", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
      { nivel: 1, equipe_a_id: "c", equipe_b_id: "d", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
      { nivel: 1, equipe_a_id: "b", equipe_b_id: "d", formato_chaveamento: "MATA_MATA", numero: 2 },
    ];

    const resultado = primeiraRodadaMataMataPorNivel(partidas);

    expect(resultado.get(1)).toBe(2);
  });

  it("nivel sem nenhuma rodada MATA_MATA ainda nao entra no mapa", () => {
    const partidas = [
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "b", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
    ];

    expect(primeiraRodadaMataMataPorNivel(partidas).has(1)).toBe(false);
  });
});

describe("integração calcularTotalRodadasPorNivel + primeiraRodadaMataMataPorNivel + nomeFase", () => {
  it("bracket de 2 equipes que comeca so na rodada 2 (pos fase de grupos) e rotulado 'Final', nao 'Rodada 2'", () => {
    // Reproduz o bug real achado testando ao vivo: Cabo de Guerra com 2
    // chaves de 2 equipes cada (rodada 1 = grupos), mata-mata final some so
    // com as 2 equipes classificadas, criado na rodada 2 (numero ABSOLUTO da
    // modalidade, nao relativo ao bracket) -- nomeFase precisa receber o
    // numero RELATIVO ao inicio do mata-mata, senao acha que a rodada 2 de
    // um bracket de 1 rodada so esta "depois do fim" (distancia negativa) e
    // cai no fallback generico.
    const partidas = [
      { nivel: 1, equipe_a_id: "a", equipe_b_id: "b", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
      { nivel: 1, equipe_a_id: "c", equipe_b_id: "d", formato_chaveamento: "TODOS_CONTRA_TODOS", numero: 1 },
      { nivel: 1, equipe_a_id: "b", equipe_b_id: "d", formato_chaveamento: "MATA_MATA", numero: 2 },
    ];

    const total = calcularTotalRodadasPorNivel(partidas);
    const inicio = primeiraRodadaMataMataPorNivel(partidas);
    const numeroAbsoluto = 2;
    const numeroRelativo = numeroAbsoluto - (inicio.get(1) ?? numeroAbsoluto) + 1;

    expect(numeroRelativo).toBe(1);
    expect(nomeFase(numeroRelativo, total.get(1))?.nome).toBe("Final");
  });
});
