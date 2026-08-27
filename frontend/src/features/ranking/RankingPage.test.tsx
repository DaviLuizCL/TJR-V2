import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RankingPage } from "./RankingPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/ranking"]}>
        <Routes>
          <Route path="/eventos/:eventoId/ranking" element={<RankingPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RankingPage", () => {
  it("mostra uma aba por modalidade liberada e a classificacao da primeira", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/ranking/modalidades") {
        return {
          data: [
            { id: "mod-1", nome: "Sumo" },
            { id: "mod-2", nome: "Danca" },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/ranking/modalidades/{modalidade_id}") {
        const params = opts as { params: { path: { modalidade_id: string } } };
        if (params.params.path.modalidade_id === "mod-1") {
          return {
            data: {
              modalidade_id: "mod-1",
              modalidade_nome: "Sumo",
              ranking_liberado: true,
              itens: [
                { equipe_id: "eq-1", equipe_nome: "Equipe A", nota_final: 50, posicao: 1 },
                { equipe_id: "eq-2", equipe_nome: "Equipe B", nota_final: 30, posicao: 2 },
              ],
            },
            error: undefined,
          } as never;
        }
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByRole("tab", { name: "Sumo" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Danca" })).toBeInTheDocument();

    const linhaA = (await screen.findByText("Equipe A")).closest("tr")!;
    expect(within(linhaA).getByText("50")).toBeInTheDocument();
  });

  it("troca de aba e busca a classificacao da modalidade escolhida", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/ranking/modalidades") {
        return {
          data: [
            { id: "mod-1", nome: "Sumo" },
            { id: "mod-2", nome: "Danca" },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/ranking/modalidades/{modalidade_id}") {
        const params = opts as { params: { path: { modalidade_id: string } } };
        const id = params.params.path.modalidade_id;
        return {
          data: {
            modalidade_id: id,
            modalidade_nome: id === "mod-1" ? "Sumo" : "Danca",
            ranking_liberado: true,
            itens:
              id === "mod-1"
                ? [{ equipe_id: "eq-1", equipe_nome: "Equipe A", nota_final: 50, posicao: 1 }]
                : [{ equipe_id: "eq-3", equipe_nome: "Equipe C", nota_final: 90, posicao: 1 }],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();
    await screen.findByText("Equipe A");

    await userEvent.click(screen.getByRole("tab", { name: "Danca" }));

    expect(await screen.findByText("Equipe C")).toBeInTheDocument();
  });

  it("mostra vitorias/derrotas/eliminado-por quando a modalidade e mata-mata", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/ranking/modalidades") {
        return { data: [{ id: "mod-1", nome: "Sumo" }], error: undefined } as never;
      }
      if (path === "/api/v1/ranking/modalidades/{modalidade_id}") {
        return {
          data: {
            modalidade_id: "mod-1",
            modalidade_nome: "Sumo",
            tipo_disputa: "CONFRONTO",
            formato_chaveamento: null,
            ranking_liberado: true,
            itens: [
              {
                equipe_id: "eq-1",
                equipe_nome: "Equipe A",
                equipe_nivel: 2,
                nota_final: 0,
                vitorias: 2,
                empates: 0,
                derrotas: 0,
                eliminado_por_nome: null,
                posicao: 1,
                formato_chaveamento: "MATA_MATA",
              },
              {
                equipe_id: "eq-2",
                equipe_nome: "Equipe B",
                equipe_nivel: 2,
                nota_final: 0,
                vitorias: 0,
                empates: 0,
                derrotas: 1,
                eliminado_por_nome: "Equipe A",
                posicao: 2,
                formato_chaveamento: "MATA_MATA",
              },
            ],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await screen.findByRole("columnheader", { name: "Eliminado por" });
    const linhas = screen.getAllByRole("row").slice(1);

    const celulasA = within(linhas[0]).getAllByRole("cell").map((celula) => celula.textContent);
    expect(celulasA).toEqual(["1º", "Equipe A", "2", "0", "-"]);
    expect(screen.queryByText(/^nota$/i)).not.toBeInTheDocument();

    const celulasB = within(linhas[1]).getAllByRole("cell").map((celula) => celula.textContent);
    expect(celulasB).toEqual(["2º", "Equipe B", "0", "1", "Equipe A"]);
  });

  it("mostra vitorias/empates/derrotas/pontos quando a modalidade e todos contra todos", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/ranking/modalidades") {
        return { data: [{ id: "mod-1", nome: "Cabo de Guerra" }], error: undefined } as never;
      }
      if (path === "/api/v1/ranking/modalidades/{modalidade_id}") {
        return {
          data: {
            modalidade_id: "mod-1",
            modalidade_nome: "Cabo de Guerra",
            tipo_disputa: "CONFRONTO",
            formato_chaveamento: null,
            ranking_liberado: true,
            itens: [
              {
                equipe_id: "eq-1",
                equipe_nome: "Equipe A",
                equipe_nivel: 3,
                nota_final: 4,
                vitorias: 1,
                empates: 1,
                derrotas: 0,
                eliminado_por_nome: null,
                posicao: 1,
                formato_chaveamento: "TODOS_CONTRA_TODOS",
              },
            ],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const linha = (await screen.findByText("Equipe A")).closest("tr")!;
    const celulas = within(linha).getAllByRole("cell").map((celula) => celula.textContent);
    expect(celulas).toEqual(["1º", "Equipe A", "1", "1", "0", "4"]);
    expect(screen.getByText(/pontos/i)).toBeInTheDocument();
  });

  it("agrupa a classificacao por nivel quando a modalidade tem mais de um nivel", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/ranking/modalidades") {
        return { data: [{ id: "mod-1", nome: "Resgate" }], error: undefined } as never;
      }
      if (path === "/api/v1/ranking/modalidades/{modalidade_id}") {
        return {
          data: {
            modalidade_id: "mod-1",
            modalidade_nome: "Resgate",
            ranking_liberado: true,
            itens: [
              { equipe_id: "eq-1", equipe_nome: "N1 Primeiro", equipe_nivel: 1, nota_final: 50, posicao: 1 },
              { equipe_id: "eq-2", equipe_nome: "N1 Segundo", equipe_nivel: 1, nota_final: 30, posicao: 2 },
              { equipe_id: "eq-3", equipe_nome: "N2 Primeiro", equipe_nivel: 2, nota_final: 1000, posicao: 1 },
            ],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const secaoNivel1 = (await screen.findByRole("heading", { name: "ABSOLUTO" })).closest("div")!;
    const secaoNivel2 = screen.getByRole("heading", { name: "Nível 2" }).closest("div")!;

    const linhaN1 = within(secaoNivel1).getByText("N1 Primeiro").closest("tr")!;
    expect(within(linhaN1).getByText("1º")).toBeInTheDocument();

    const linhaN2 = within(secaoNivel2).getByText("N2 Primeiro").closest("tr")!;
    expect(within(linhaN2).getByText("1º")).toBeInTheDocument();

    // As duas secoes tem cada uma o seu proprio "1o lugar" — nao existe um
    // "1o geral" que teria escondido o campeao do outro nivel.
    expect(within(secaoNivel1).getByText("N1 Segundo")).toBeInTheDocument();
  });

  it("mostra mensagem quando nenhuma modalidade tem ranking liberado", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/ranking/modalidades") {
        return { data: [], error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText(/nenhum ranking liberado/i)).toBeInTheDocument();
  });
});
