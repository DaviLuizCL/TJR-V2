import createClient from "openapi-fetch";

import { useAuthStore } from "../lib/auth-store";
import type { paths } from "./types";

const baseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({
  baseUrl,
  // openapi-fetch captura `globalThis.fetch` uma unica vez, na criacao do
  // client - sem esse encaminhamento indireto, um teste que troca
  // `globalThis.fetch` depois desse modulo ja ter sido importado nunca
  // seria observado (o client continuaria usando a referencia antiga).
  fetch: (request) => globalThis.fetch(request),
});

// Guarda uma copia (nao consumida) de cada requisicao em voo, pra poder
// reenvia-la com o token renovado se ela vier a receber 401. Precisa ser
// clonada aqui, antes do fetch de fato consumir o corpo da requisicao.
const requisicoesEmVoo = new Map<string, Request>();

let renovacaoEmAndamento: Promise<string | null> | null = null;

async function renovarSessao(): Promise<string | null> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) return null;

  if (!renovacaoEmAndamento) {
    renovacaoEmAndamento = (async () => {
      try {
        const resposta = await globalThis.fetch(`${baseUrl}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!resposta.ok) return null;

        const dados = (await resposta.json()) as { access_token: string; refresh_token: string };
        useAuthStore.getState().atualizarTokens({
          accessToken: dados.access_token,
          refreshToken: dados.refresh_token,
        });
        return dados.access_token;
      } catch {
        return null;
      } finally {
        renovacaoEmAndamento = null;
      }
    })();
  }

  return renovacaoEmAndamento;
}

api.use({
  onRequest({ request, id }) {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    requisicoesEmVoo.set(id, request.clone());
    return request;
  },
  async onResponse({ response, id }) {
    const requisicaoOriginal = requisicoesEmVoo.get(id);
    requisicoesEmVoo.delete(id);

    if (response.status !== 401) {
      return response;
    }

    const novoToken = await renovarSessao();
    if (!novoToken || !requisicaoOriginal) {
      useAuthStore.getState().sair();
      return response;
    }

    requisicaoOriginal.headers.set("Authorization", `Bearer ${novoToken}`);
    return globalThis.fetch(requisicaoOriginal);
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
