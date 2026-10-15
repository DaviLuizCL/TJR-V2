import { create } from "zustand";

export type TipoAviso = "sucesso" | "erro" | "alerta" | "info";

export interface AvisoFlutuante {
  id: number;
  tipo: TipoAviso;
  mensagem: string;
}

interface AvisosState {
  avisos: AvisoFlutuante[];
  fechar: (id: number) => void;
}

const DURACAO_MS = 3500;
let proximoId = 1;

export const useAvisosStore = create<AvisosState>((set) => ({
  avisos: [],
  fechar: (id) => set((state) => ({ avisos: state.avisos.filter((a) => a.id !== id) })),
}));

// Toast que some sozinho. Pode ser chamado de qualquer lugar (fora de componente
// tambem); quem desenha e o <AvisosFlutuantes /> montado no App.
export function avisar(tipo: TipoAviso, mensagem: string): void {
  const id = proximoId++;
  useAvisosStore.setState((state) => ({ avisos: [...state.avisos, { id, tipo, mensagem }] }));
  setTimeout(() => useAvisosStore.getState().fechar(id), DURACAO_MS);
}

// Depois de gravar uma nota na fila local: so diz "enviada" se tem rede pra isso.
export function avisarPontuacaoRegistrada(): void {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    avisar("info", "Sem internet: pontuação guardada no celular, vai sozinha quando a rede voltar.");
    return;
  }
  avisar("sucesso", "Pontuação enviada!");
}
