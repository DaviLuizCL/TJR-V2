export interface FaseInfo {
  nome: string;
  classes: string;
}

const NOMES_FASE = ["Final", "Semifinal", "Quartas de Final", "Oitavas de Final"];
const CLASSES_FASE = [
  "bg-amber-100 text-amber-800 border border-amber-300",
  "bg-sky-100 text-sky-800 border border-sky-300",
  "bg-slate-100 text-slate-700 border border-slate-300",
  "bg-slate-100 text-slate-700 border border-slate-300",
];

/**
 * Nome de fase de bracket (mata-mata) a partir de quantas
 * rodadas o nivel precisa no total pra decidir o campeao. Retorna null
 * quando nao da pra saber o total (nivel ainda sem nenhuma partida na
 * rodada 1) ou quando o bracket e grande demais pra ter nome usual (mais de
 * 16 equipes) - nesses casos o chamador cai de volta pra "Rodada N".
 */
export function nomeFase(numero: number, totalRodadas: number | undefined): FaseInfo | null {
  if (!totalRodadas || totalRodadas <= 0) return null;
  const distancia = totalRodadas - numero;
  if (distancia < 0 || distancia >= NOMES_FASE.length) return null;
  return { nome: NOMES_FASE[distancia], classes: CLASSES_FASE[distancia] };
}

export interface PartidaParaFase {
  nivel: number | null;
  equipe_a_id: string;
  equipe_b_id: string | null;
  formato_chaveamento?: string;
  numero: number;
}

/**
 * Quantas rodadas cada nivel precisa ate a final, a partir de quantas
 * equipes unicas apareceram na PRIMEIRA rodada MATA_MATA desse nivel
 * (ceil(log2(equipes))). Funciona com qualquer distribuicao de byes, ja que
 * o numero de rodadas de um bracket so depende da quantidade de equipes, nao
 * de como os byes caem.
 *
 * Antes assumia que a rodada 1 da modalidade e sempre o inicio do bracket --
 * deixou de valer com a fase de grupos (uma Chave joga TODOS_CONTRA_TODOS
 * nas primeiras rodadas; o mata-mata so comeca depois, numa rodada
 * qualquer). Por isso o calculo agora acha, por nivel, a rodada de menor
 * `numero` cujas partidas sao `MATA_MATA`, e conta equipes so ali. Nivel que
 * ainda nao teve nenhuma rodada MATA_MATA (so fase de grupos, ou nada ainda)
 * simplesmente nao entra no resultado -- os chamadores ja tratam "sem total"
 * caindo pro rotulo generico "Rodada N".
 */
/**
 * Menor `numero` de rodada, por nivel, cujas partidas sao `MATA_MATA` -- o
 * inicio "de verdade" do bracket daquele nivel. Antes da fase de grupos
 * isso sempre coincidia com a rodada 1 (unico caso que existia); agora pode
 * ser qualquer numero (rodadas anteriores foram fase de grupos). Nivel sem
 * nenhuma rodada MATA_MATA ainda (so grupos, ou nada) nao entra no mapa.
 */
export function primeiraRodadaMataMataPorNivel(partidas: PartidaParaFase[]): Map<number, number> {
  const resultado = new Map<number, number>();
  for (const partida of partidas) {
    if (partida.nivel == null || partida.formato_chaveamento !== "MATA_MATA") continue;
    const atual = resultado.get(partida.nivel);
    if (atual == null || partida.numero < atual) {
      resultado.set(partida.nivel, partida.numero);
    }
  }
  return resultado;
}

export function calcularTotalRodadasPorNivel(partidas: PartidaParaFase[]): Map<number, number> {
  const inicioPorNivel = primeiraRodadaMataMataPorNivel(partidas);

  const equipesPorNivel = new Map<number, Set<string>>();
  for (const partida of partidas) {
    if (partida.nivel == null) continue;
    if (partida.numero !== inicioPorNivel.get(partida.nivel)) continue;
    if (!equipesPorNivel.has(partida.nivel)) equipesPorNivel.set(partida.nivel, new Set());
    equipesPorNivel.get(partida.nivel)!.add(partida.equipe_a_id);
    if (partida.equipe_b_id) equipesPorNivel.get(partida.nivel)!.add(partida.equipe_b_id);
  }
  const resultado = new Map<number, number>();
  for (const [nivel, equipes] of equipesPorNivel) {
    resultado.set(nivel, Math.ceil(Math.log2(equipes.size)));
  }
  return resultado;
}
