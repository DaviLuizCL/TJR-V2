import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Usuario {
  id: string;
  nome: string;
  email: string;
  papel: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  usuario: Usuario | null;
  definirSessao: (params: {
    accessToken: string;
    refreshToken: string;
    usuario: Usuario;
  }) => void;
  atualizarTokens: (params: { accessToken: string; refreshToken: string }) => void;
  sair: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      usuario: null,
      definirSessao: ({ accessToken, refreshToken, usuario }) =>
        set({ accessToken, refreshToken, usuario }),
      atualizarTokens: ({ accessToken, refreshToken }) => set({ accessToken, refreshToken }),
      sair: () => set({ accessToken: null, refreshToken: null, usuario: null }),
    }),
    { name: "tjr-auth" },
  ),
);
