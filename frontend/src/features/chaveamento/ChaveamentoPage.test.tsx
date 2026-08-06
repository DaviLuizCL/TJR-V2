import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ChaveamentoPage } from "./ChaveamentoPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/chaveamento"]}>
        <Routes>
          <Route path="/eventos/:eventoId/chaveamento" element={<ChaveamentoPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ChaveamentoPage", () => {
  it("mostra as rodadas em colunas com as partidas e destaca o vencedor", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              {
                id: "mod-1",
                nome: "Combate Mata-Mata",
                tipo_disputa: "CONFRONTO",
                formato_chaveamento: "MATA_MATA",
              },
              { id: "mod-2", nome: "Danca", tipo_disputa: "INDIVIDUAL", formato_chaveamento: null },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: {
            itens: [{ id: "rod-1", modalidade_id: "mod-1", numero: 1 }],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return {
          data: [
            {
              id: "p1",
              equipe_a_id: "eq-1",
              equipe_b_id: "eq-2",
              vencedor_id: "eq-2",
              status: "ENCERRADA",
              nivel: 1,
            },
            {
              id: "p2",
              equipe_a_id: "eq-3",
              equipe_b_id: null,
              vencedor_id: "eq-3",
              status: "ENCERRADA",
              nivel: 1,
            },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe A", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe B", nivel: 1, ativo: true },
              { id: "eq-3", nome: "Equipe C", nivel: 1, ativo: true },
            ],
            total: 3,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      const opt = opts as never;
      void opt;
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText("Rodada 1")).toBeInTheDocument();
    const vencedor = await screen.findByText("Equipe B");
    expect(vencedor.className).toMatch(/emerald/);
    const perdedor = await screen.findByText("Equipe A");
    expect(perdedor.className).not.toMatch(/emerald/);
    expect(await screen.findByText("(bye)")).toBeInTheDocument();

    const seletorModalidade = screen.getByLabelText(/modalidade/i);
    expect(within(seletorModalidade).getByText("Combate Mata-Mata")).toBeInTheDocument();
    expect(within(seletorModalidade).queryByText("Danca")).not.toBeInTheDocument();

    // um unico nivel presente nas partidas: nao mostra seletor de nivel
    expect(screen.queryByLabelText(/^nivel$/i)).not.toBeInTheDocument();
  });

  it("mostra mensagem quando o evento nao tem modalidade de combate", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "mod-2", nome: "Danca", tipo_disputa: "INDIVIDUAL", formato_chaveamento: null }],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText(/nenhuma modalidade de combate/i)).toBeInTheDocument();
  });

  it("lista modalidade todos-contra-todos tambem, nao so mata-mata", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              {
                id: "mod-3",
                nome: "Cabo de Guerra",
                tipo_disputa: "CONFRONTO",
                formato_chaveamento: "TODOS_CONTRA_TODOS",
              },
              { id: "mod-2", nome: "Danca", tipo_disputa: "INDIVIDUAL", formato_chaveamento: null },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
      }
      if (path === "/api/v1/equipes") {
        return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const seletorModalidade = await screen.findByLabelText(/modalidade/i);
    expect(within(seletorModalidade).getByText("Cabo de Guerra")).toBeInTheDocument();
    expect(within(seletorModalidade).queryByText("Danca")).not.toBeInTheDocument();
  });

  it("mostra seletor de nivel e filtra as colunas pelo nivel escolhido", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              {
                id: "mod-1",
                nome: "Sumo",
                tipo_disputa: "CONFRONTO",
                formato_chaveamento: "MATA_MATA",
              },
            ],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: { itens: [{ id: "rod-1", modalidade_id: "mod-1", numero: 1 }], total: 1, page: 1, size: 200 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return {
          data: [
            {
              id: "p1",
              equipe_a_id: "eq-1",
              equipe_b_id: "eq-2",
              vencedor_id: null,
              status: "AGENDADA",
              nivel: 1,
            },
            {
              id: "p2",
              equipe_a_id: "eq-3",
              equipe_b_id: "eq-4",
              vencedor_id: null,
              status: "AGENDADA",
              nivel: 2,
            },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe Nivel 1 A", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe Nivel 1 B", nivel: 1, ativo: true },
              { id: "eq-3", nome: "Equipe Nivel 2 A", nivel: 2, ativo: true },
              { id: "eq-4", nome: "Equipe Nivel 2 B", nivel: 2, ativo: true },
            ],
            total: 4,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      const opt = opts as never;
      void opt;
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText("Equipe Nivel 1 A")).toBeInTheDocument();
    expect(screen.getByText("Equipe Nivel 1 B")).toBeInTheDocument();
    expect(screen.queryByText("Equipe Nivel 2 A")).not.toBeInTheDocument();

    const seletorNivel = screen.getByLabelText(/^nivel$/i);
    await userEvent.selectOptions(seletorNivel, "2");

    expect(await screen.findByText("Equipe Nivel 2 A")).toBeInTheDocument();
    expect(screen.getByText("Equipe Nivel 2 B")).toBeInTheDocument();
    expect(screen.queryByText("Equipe Nivel 1 A")).not.toBeInTheDocument();
  });

  it("mostra banner de campeao quando o mata-mata do nivel ja tem 1 partida encerrada na ultima rodada", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "mod-1", nome: "Sumo", tipo_disputa: "CONFRONTO", formato_chaveamento: "MATA_MATA" },
            ],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: { itens: [{ id: "rod-1", modalidade_id: "mod-1", numero: 1 }], total: 1, page: 1, size: 200 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return {
          data: [
            {
              id: "p1",
              equipe_a_id: "eq-1",
              equipe_b_id: "eq-2",
              vencedor_id: "eq-1",
              status: "ENCERRADA",
              nivel: 1,
            },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe Campea", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe B", nivel: 1, ativo: true },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText(/campe[ãa]o/i)).toBeInTheDocument();
    expect(screen.getByText(/campe[ãa]o/i).textContent).toMatch(/Equipe Campea/);
  });

  it("mostra banner de returno finalizado quando todas as partidas do nivel ja foram decididas", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              {
                id: "mod-1",
                nome: "Cabo de Guerra",
                tipo_disputa: "CONFRONTO",
                formato_chaveamento: "TODOS_CONTRA_TODOS",
              },
            ],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: { itens: [{ id: "rod-1", modalidade_id: "mod-1", numero: 1 }], total: 1, page: 1, size: 200 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return {
          data: [
            {
              id: "p1",
              equipe_a_id: "eq-1",
              equipe_b_id: "eq-2",
              vencedor_id: "eq-1",
              status: "ENCERRADA",
              nivel: 1,
            },
            {
              id: "p2",
              equipe_a_id: "eq-3",
              equipe_b_id: "eq-4",
              vencedor_id: null,
              status: "EMPATADA",
              nivel: 1,
            },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText(/returno finalizado/i)).toBeInTheDocument();
  });

  it("troca de modalidade ao selecionar outra no seletor", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "mod-1", nome: "Sumo", tipo_disputa: "CONFRONTO", formato_chaveamento: "MATA_MATA" },
              {
                id: "mod-2",
                nome: "Faca-Cega",
                tipo_disputa: "CONFRONTO",
                formato_chaveamento: "TODOS_CONTRA_TODOS",
              },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        const params = opts as { params: { query: { modalidade_id: string } } };
        const modalidadeId = params.params.query.modalidade_id;
        return {
          data: {
            itens: [{ id: `rod-${modalidadeId}`, modalidade_id: modalidadeId, numero: 1 }],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return { data: [], error: undefined } as never;
      }
      if (path === "/api/v1/equipes") {
        return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const seletor = await screen.findByLabelText(/modalidade/i);
    await userEvent.selectOptions(seletor, "mod-2");

    expect(await screen.findByText("Rodada 1")).toBeInTheDocument();
  });
});
