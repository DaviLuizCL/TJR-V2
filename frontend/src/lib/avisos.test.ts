import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { avisar, useAvisosStore } from "./avisos";

describe("avisos (toast)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useAvisosStore.setState({ avisos: [] });
  });
  afterEach(() => vi.useRealTimers());

  it("avisar empilha o aviso com tipo e mensagem", () => {
    avisar("sucesso", "Pontuação enviada!");

    expect(useAvisosStore.getState().avisos).toEqual([
      expect.objectContaining({ tipo: "sucesso", mensagem: "Pontuação enviada!" }),
    ]);
  });

  it("o aviso some sozinho depois de alguns segundos", () => {
    avisar("info", "Oi");
    vi.advanceTimersByTime(5000);

    expect(useAvisosStore.getState().avisos).toEqual([]);
  });

  it("fechar remove so o aviso escolhido", () => {
    avisar("erro", "Primeiro");
    avisar("alerta", "Segundo");
    const [primeiro] = useAvisosStore.getState().avisos;

    useAvisosStore.getState().fechar(primeiro.id);

    expect(useAvisosStore.getState().avisos.map((a) => a.mensagem)).toEqual(["Segundo"]);
  });
});
