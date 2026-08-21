import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PainelPage } from "./PainelPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/painel"]}>
        <Routes>
          <Route path="/eventos/:eventoId/painel" element={<PainelPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockGet() {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades") {
      return {
        data: {
          itens: [
            { id: "mod-1", nome: "Sumo", tipo_disputa: "CONFRONTO", status: "PUBLICADA" },
            { id: "mod-2", nome: "Danca", tipo_disputa: "INDIVIDUAL", status: "PUBLICADA" },
          ],
          total: 2,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/ranking/modalidades/{modalidade_id}") {
      return {
        data: {
          modalidade_id: "mod-1",
          modalidade_nome: "Sumo",
          ranking_liberado: false,
          itens: [{ equipe_id: "eq-1", equipe_nome: "Equipe A", nota_final: 50, posicao: 1 }],
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/lancamentos/auditoria") {
      return {
        data: {
          itens: [
            {
              id: "lanc-1",
              modalidade_nome: "Sumo",
              nivel: 2,
              equipe_nome: "Equipe A",
              rodada_numero: 1,
              tentativa: 1,
              responsavel_nome: "Joana Arbitra",
              horario_submissao: "2026-03-10T12:00:00Z",
              status: "CONFIRMADO",
              total: 55,
              itens: [
                {
                  criterio_snapshot: { nome: "Lombada", categoria: "PONTUACAO" },
                  pontos: 30,
                },
                {
                  criterio_snapshot: { nome: "Curva perfeita", categoria: "PONTUACAO" },
                  pontos: 0,
                },
                {
                  criterio_snapshot: { nome: "Saiu da area", categoria: "PENALIDADE" },
                  pontos: -5,
                },
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

describe("PainelPage", () => {
  it("nao mostra mais a aba Ranking (ocultada temporariamente) e vai direto pras submissoes", async () => {
    mockGet();

    renderPage();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(card).getByText(/Sumo/)).toBeInTheDocument();

    expect(screen.queryByRole("tab", { name: /ranking/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Sumo" })).not.toBeInTheDocument();
  });

  it("mostra os cards de auditoria de submissoes", async () => {
    mockGet();

    renderPage();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(card).getByText(/Sumo/)).toBeInTheDocument();
    expect(within(card).getByText(/Nivel 2/)).toBeInTheDocument();
    expect(within(card).getByText("55")).toBeInTheDocument();
    expect(within(card).getByText("Lombada: 30")).toBeInTheDocument();
    expect(within(card).getByText("Curva perfeita")).toBeInTheDocument();
    expect(within(card).getByText("Saiu da area: -5")).toBeInTheDocument();
  });

  it("filtra as submissoes por modalidade", async () => {
    mockGet();

    renderPage();
    await screen.findByText("Joana Arbitra");

    const selectModalidade = screen.getByLabelText(/filtrar por modalidade/i);
    await userEvent.selectOptions(selectModalidade, "mod-1");

    await waitFor(() =>
      expect(api.GET).toHaveBeenCalledWith(
        "/api/v1/lancamentos/auditoria",
        expect.objectContaining({
          params: { query: expect.objectContaining({ modalidade_id: "mod-1" }) },
        }),
      ),
    );
  });
});
