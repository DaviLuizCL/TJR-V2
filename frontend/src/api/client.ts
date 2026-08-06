import createClient from "openapi-fetch";

import { useAuthStore } from "../lib/auth-store";
import type { paths } from "./types";

const baseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl });

api.use({
  onRequest({ request }) {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401) {
      useAuthStore.getState().sair();
    }
    return response;
  },
});

export interface ErroApi {
  codigo: string;
  mensagem: string;
  detalhes: Record<string, unknown>;
}

const ERRO_GENERICO: ErroApi = {
  codigo: "ERRO_DESCONHECIDO",
  mensagem: "Ocorreu um erro inesperado. Tente novamente.",
  detalhes: {},
};

export function extrairErro(error: unknown): ErroApi {
  if (error && typeof error === "object" && "erro" in error) {
    const erro = (error as { erro: unknown }).erro;
    if (erro && typeof erro === "object" && "codigo" in erro && "mensagem" in erro) {
      return erro as ErroApi;
    }
  }
  return ERRO_GENERICO;
}
