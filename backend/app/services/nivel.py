def rotulo_nivel(nivel: int) -> str:
    # Mesmo rotulo do front (lib/nivel.ts). ABSOLUTO e o nivel 0, igual a
    # planilha oficial; ate 23/10/2026 o nivel 1 era reaproveitado pra isso.
    return "ABSOLUTO" if nivel == 0 else f"Nível {nivel}"
