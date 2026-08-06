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

/**
 * Quantas rodadas cada nivel precisa ate a final, a partir de quantas
 * equipes unicas apareceram na rodada 1 desse nivel (ceil(log2(equipes))).
 * Funciona com qualquer distribuicao de byes, ja que o numero de rodadas de
 * um bracket so depende da quantidade de equipes, nao de como os byes caem.
 */
export function calcularTotalRodadasPorNivel(
  partidasRodada1: { nivel: number | null; equipe_a_id: string; equipe_b_id: string | null }[],
): Map<number, number> {
  const equipesPorNivel = new Map<number, Set<string>>();
  for (const partida of partidasRodada1) {
    if (partida.nivel == null) continue;
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
