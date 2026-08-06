import { create } from "zustand";
import { persist } from "zustand/middleware";

interface EventoState {
  eventoAtualId: string | null;
  definirEventoAtual: (eventoId: string) => void;
}

export const useEventoStore = create<EventoState>()(
  persist(
    (set) => ({
      eventoAtualId: null,
      definirEventoAtual: (eventoId) => set({ eventoAtualId: eventoId }),
    }),
    { name: "tjr-evento-atual" },
  ),
);
