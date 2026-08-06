import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { EquipeSubmissoesPage } from "./EquipeSubmissoesPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/equipes/eq-1/submissoes"]}>
        <Routes>
          <Route path="/equipes/:equipeId/submissoes" element={<EquipeSubmissoesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockGet() {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/equipes/{equipe_id}") {
      return {
        data: { id: "eq-1", nome: "Equipe Foguete", nivel: 2, ativo: true },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/lancamentos/auditoria") {
      return {
        data: {
          itens: [
            {
              id: "lanc-1",
              modalidade_nome: "Viagem ao Centro da Terra",
              nivel: 2,
              equipe_nome: "Equipe Foguete",
              rodada_numero: 1,
              tentativa: 1,
              responsavel_nome: "Joana Arbitra",
              horario_submissao: "2026-03-10T12:00:00Z",
              status: "CONFIRMADO",
              total: 45,
              itens: [
                { criterio_snapshot: { nome: "Entregou 1o cubo", categoria: "PONTUACAO" }, pontos: 45 },
              ],
            },
          ],
          total: 1,
          page: 1,
          size: 100,
        },
        error: undefined,
      } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("EquipeSubmissoesPage", () => {
  it("mostra o nome da equipe no titulo", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByRole("heading", { name: /equipe foguete/i })).toBeInTheDocument();
  });

  it("lista todas as pontuacoes da equipe em qualquer modalidade, filtrando pelo equipe_id certo", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByText(/viagem ao centro da terra/i)).toBeInTheDocument();
    expect(screen.getByText("45")).toBeInTheDocument();

    expect(api.GET).toHaveBeenCalledWith(
      "/api/v1/lancamentos/auditoria",
      expect.objectContaining({
        params: { query: expect.objectContaining({ equipe_id: "eq-1" }) },
      }),
    );
  });
});
