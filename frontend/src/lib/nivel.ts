/**
 * Rotulo de exibicao pro nivel de uma equipe/modalidade. Nivel 1 nunca foi
 * usado por nenhuma modalidade real -- foi reaproveitado como "ABSOLUTO"
 * (nivel 0 na planilha oficial, tudo misturado), sem migration: o inteiro no
 * banco continua 1, so o rotulo muda.
 */
export function rotuloNivel(nivel: number): string {
  return nivel === 1 ? "ABSOLUTO" : `Nível ${nivel}`;
}
