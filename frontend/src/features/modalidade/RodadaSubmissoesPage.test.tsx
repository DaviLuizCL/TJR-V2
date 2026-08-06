import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RodadaSubmissoesPage } from "./RodadaSubmissoesPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/submissoes"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas/:rodadaId/submissoes"
            element={<RodadaSubmissoesPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockGet() {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return { data: { id: "mod-1", nome: "Resgate no Plano" }, error: undefined } as never;
    }
    if (path === "/api/v1/rodadas/{rodada_id}") {
      return {
        data: { id: "rod-1", modalidade_id: "mod-1", numero: 2, status: "EM_ANDAMENTO" },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/lancamentos/auditoria") {
      return {
        data: {
          itens: [
            {
              id: "lanc-1",
              modalidade_nome: "Resgate no Plano",
              nivel: 1,
              equipe_nome: "Equipe Foguete",
              rodada_numero: 2,
              tentativa: 1,
              responsavel_nome: "Joana Arbitra",
              horario_submissao: "2026-03-10T12:00:00Z",
              status: "CONFIRMADO",
              total: 40,
              itens: [
                { criterio_snapshot: { nome: "Resgatou vitima", categoria: "PONTUACAO" }, pontos: 40 },
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

describe("RodadaSubmissoesPage", () => {
  it("mostra o titulo com modalidade e numero da rodada", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByText(/resgate no plano/i)).toBeInTheDocument();
    expect(screen.getByText(/rodada 2/i)).toBeInTheDocument();
  });

  it("lista as fichas enviadas nessa rodada, filtrando pelo rodada_id certo", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByText(/equipe foguete/i)).toBeInTheDocument();
    expect(screen.getByText("Joana Arbitra")).toBeInTheDocument();

    expect(api.GET).toHaveBeenCalledWith(
      "/api/v1/lancamentos/auditoria",
      expect.objectContaining({
        params: { query: expect.objectContaining({ rodada_id: "rod-1" }) },
      }),
    );
  });
});
