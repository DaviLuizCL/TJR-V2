/**
 * Rotulo de exibicao pro nivel de uma equipe/modalidade. ABSOLUTO e o nivel 0,
 * igual a planilha oficial (tudo misturado, sem separar por idade). Ate
 * 23/10/2026 o nivel 1 era reaproveitado como ABSOLUTO; agora o Nivel 1 existe
 * de verdade, separado.
 */
export function rotuloNivel(nivel: number): string {
  return nivel === 0 ? "ABSOLUTO" : `Nível ${nivel}`;
}
