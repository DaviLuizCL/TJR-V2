import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { InscricaoPage } from "./InscricaoPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/inscricoes"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/inscricoes"
            element={<InscricaoPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockGet({
  inscricoes = [],
}: {
  inscricoes?: { id: string; equipe_id: string; modalidade_id: string }[];
}) {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return {
        data: { id: "mod-1", nome: "Sumo de Robos", niveis_aplicaveis: [1, 2] },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/equipes") {
      return {
        data: {
          itens: [
            { id: "eq1", nome: "Equipe Alpha", nivel: 1, ativo: true },
            { id: "eq2", nome: "Equipe Beta", nivel: 2, ativo: true },
            { id: "eq3", nome: "Equipe Fora De Nivel", nivel: 4, ativo: true },
          ],
          total: 3,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/inscricoes") {
      return {
        data: { itens: inscricoes, total: inscricoes.length, page: 1, size: 100 },
        error: undefined,
      } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("InscricaoPage", () => {
  it("lista as equipes ja inscritas na modalidade", async () => {
    mockGet({ inscricoes: [{ id: "ins1", equipe_id: "eq1", modalidade_id: "mod-1" }] });

    renderPage();

    expect(await screen.findByText("Equipe Alpha")).toBeInTheDocument();
  });

  it("so oferece para inscricao equipes cujo nivel e aplicavel a modalidade", async () => {
    mockGet({ inscricoes: [] });

    renderPage();

    await screen.findByRole("button", { name: /inscrever/i });
    const select = screen.getByLabelText(/equipe/i);
    const opcoes = within(select).getAllByRole("option").map((o) => o.textContent);

    expect(opcoes.some((texto) => texto?.includes("Equipe Alpha"))).toBe(true);
    expect(opcoes.some((texto) => texto?.includes("Equipe Fora De Nivel"))).toBe(false);
  });

  it("inscreve uma equipe selecionada", async () => {
    mockGet({ inscricoes: [] });
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "ins-nova", equipe_id: "eq1", modalidade_id: "mod-1" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/equipe/i), "eq1");
    await userEvent.click(screen.getByRole("button", { name: /inscrever/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/inscricoes",
        expect.objectContaining({ body: { equipe_id: "eq1", modalidade_id: "mod-1" } }),
      ),
    );
  });

  it("remove a inscricao de uma equipe", async () => {
    mockGet({ inscricoes: [{ id: "ins1", equipe_id: "eq1", modalidade_id: "mod-1" }] });
    vi.mocked(api.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);

    renderPage();

    const botao = await screen.findByRole("button", { name: /remover/i });
    await userEvent.click(botao);

    await waitFor(() =>
      expect(api.DELETE).toHaveBeenCalledWith(
        "/api/v1/inscricoes/{inscricao_id}",
        expect.objectContaining({ params: { path: { inscricao_id: "ins1" } } }),
      ),
    );
  });
});
