import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../lib/auth-store";
import { api } from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  useAuthStore.setState({
    accessToken: "token-expirado",
    refreshToken: "refresh-valido",
    usuario: { id: "u1", nome: "Teste", email: "t@tjr.app", papel: "COORDENADOR" },
  });
});

describe("client — renovação de sessão em 401", () => {
  it("ao receber 401, chama /auth/refresh e repete a requisição original com o novo token", async () => {
    let chamada = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/api/v1/auth/refresh")) {
        return jsonResponse({
          access_token: "token-novo",
          refresh_token: "refresh-novo",
          token_type: "bearer",
        });
      }
      if (url.includes("/api/v1/equipes")) {
        chamada += 1;
        if (chamada === 1) {
          return jsonResponse({ erro: { codigo: "TOKEN_EXPIRADO", mensagem: "Expirado." } }, 401);
        }
        return jsonResponse({ itens: [], total: 0, page: 1, size: 50 });
      }
      throw new Error(`URL inesperada no teste: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { data, error } = await api.GET("/api/v1/equipes", { params: { query: { size: 50 } } });

    expect(error).toBeUndefined();
    expect(data).toEqual({ itens: [], total: 0, page: 1, size: 50 });
    expect(chamada).toBe(2);
    expect(useAuthStore.getState().accessToken).toBe("token-novo");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-novo");

    const chamadasParaEquipes = fetchMock.mock.calls.filter(([input]) =>
      (typeof input === "string" ? input : (input as Request).url).includes("/api/v1/equipes"),
    );
    const chamadaRetry = chamadasParaEquipes[chamadasParaEquipes.length - 1];
    const requestRetry = chamadaRetry?.[0] as Request;
    expect(requestRetry.headers.get("Authorization")).toBe("Bearer token-novo");

    vi.unstubAllGlobals();
  });

  it("se o refresh tambem falhar, encerra a sessao (sair)", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/api/v1/auth/refresh")) {
        return jsonResponse({ erro: { codigo: "TOKEN_INVALIDO", mensagem: "Invalido." } }, 401);
      }
      if (url.includes("/api/v1/equipes")) {
        return jsonResponse({ erro: { codigo: "TOKEN_EXPIRADO", mensagem: "Expirado." } }, 401);
      }
      throw new Error(`URL inesperada no teste: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.GET("/api/v1/equipes", { params: { query: { size: 50 } } });

    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
    expect(useAuthStore.getState().usuario).toBeNull();

    vi.unstubAllGlobals();
  });

  it("duas requisicoes que recebem 401 ao mesmo tempo so chamam /auth/refresh uma vez", async () => {
    let chamadasRefresh = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/api/v1/auth/refresh")) {
        chamadasRefresh += 1;
        return jsonResponse({
          access_token: "token-novo",
          refresh_token: "refresh-novo",
          token_type: "bearer",
        });
      }
      if (url.includes("/api/v1/equipes") || url.includes("/api/v1/modalidades")) {
        const request = input as Request;
        if (request.headers.get("Authorization") === "Bearer token-expirado") {
          return jsonResponse({ erro: { codigo: "TOKEN_EXPIRADO", mensagem: "Expirado." } }, 401);
        }
        return jsonResponse({ itens: [], total: 0, page: 1, size: 50 });
      }
      throw new Error(`URL inesperada no teste: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const [r1, r2] = await Promise.all([
      api.GET("/api/v1/equipes", { params: { query: { size: 50 } } }),
      api.GET("/api/v1/modalidades", { params: { query: { size: 50 } } }),
    ]);

    expect(r1.error).toBeUndefined();
    expect(r2.error).toBeUndefined();
    expect(chamadasRefresh).toBe(1);

    vi.unstubAllGlobals();
  });
});
