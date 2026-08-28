import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ChaveamentoManualBuilder } from "./ChaveamentoManualBuilder";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderBuilder(onFechar = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChaveamentoManualBuilder modalidadeId="mod-1" onFechar={onFechar} />
    </QueryClientProvider>,
  );
}

function mockDados(partidasExistentes: Record<string, unknown>[] = []) {
  vi.mocked(api.GET).mockImplementation(async (path: unknown, opts?: unknown) => {
    if (path === "/api/v1/equipes") {
      return {
        data: {
          itens: [
            { id: "eq-a", nome: "Equipe A", nivel: 2, ativo: true },
            { id: "eq-b", nome: "Equipe B", nivel: 2, ativo: true },
            { id: "eq-c", nome: "Equipe C", nivel: 2, ativo: true },
            { id: "eq-d", nome: "Equipe D", nivel: 3, ativo: true },
            { id: "eq-e", nome: "Equipe E", nivel: 3, ativo: true },
          ],
          total: 5,
          page: 1,
          size: 1000,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/inscricoes") {
      const query = (opts as { params?: { query?: Record<string, unknown> } })?.params?.query;
      if (query?.modalidade_id !== "mod-1") {
        return { data: { itens: [], total: 0, page: 1, size: 1000 }, error: undefined } as never;
      }
      return {
        data: {
          itens: [
            { equipe_id: "eq-a", modalidade_id: "mod-1" },
            { equipe_id: "eq-b", modalidade_id: "mod-1" },
            { equipe_id: "eq-c", modalidade_id: "mod-1" },
            { equipe_id: "eq-d", modalidade_id: "mod-1" },
            { equipe_id: "eq-e", modalidade_id: "mod-1" },
          ],
          total: 5,
          page: 1,
          size: 1000,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/rodadas") {
      if (partidasExistentes.length === 0) {
        return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
      }
      return {
        data: { itens: [{ id: "r1", numero: 1 }], total: 1, page: 1, size: 200 },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
      return { data: partidasExistentes, error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ChaveamentoManualBuilder", () => {
  it("mostra as equipes elegiveis do nivel selecionado nos dois seletores", async () => {
    mockDados();
    renderBuilder();

    const selectA = screen.getByLabelText(/equipe a/i);
    await within(selectA).findByText("Equipe A");
    expect(within(selectA).getByText("Equipe B")).toBeInTheDocument();
    expect(within(selectA).queryByText("Equipe D")).not.toBeInTheDocument();
  });

  it("equipe que ja tem partida some dos seletores e aparece no card", async () => {
    mockDados([
      {
        id: "p1",
        equipe_a_id: "eq-a",
        equipe_b_id: "eq-b",
        nivel: 2,
        status: "AGENDADA",
        formato_chaveamento: "MATA_MATA",
      },
    ]);
    renderBuilder();

    const selectA = screen.getByLabelText(/equipe a/i);
    await within(selectA).findByText("Equipe C");
    await waitFor(() =>
      expect(within(selectA).queryByText("Equipe A")).not.toBeInTheDocument(),
    );
    expect(within(selectA).queryByText("Equipe B")).not.toBeInTheDocument();
    expect(await screen.findByText(/equipe a.*x.*equipe b/i)).toBeInTheDocument();
  });

  it("salva um confronto com as duas equipes escolhidas", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "p-nova", equipe_a_id: "eq-a", equipe_b_id: "eq-b" },
      error: undefined,
    } as never);
    renderBuilder();

    const selectA = screen.getByLabelText(/equipe a/i);
    await within(selectA).findByText("Equipe A");
    await userEvent.selectOptions(selectA, "eq-a");
    await userEvent.selectOptions(screen.getByLabelText(/equipe b/i), "eq-b");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        expect.objectContaining({
          params: { path: { modalidade_id: "mod-1" } },
          body: { equipe_a_id: "eq-a", equipe_b_id: "eq-b" },
        }),
      ),
    );
  });

  it("salva um bye quando 'sem adversario' e escolhido", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "p-nova", equipe_a_id: "eq-a", equipe_b_id: null },
      error: undefined,
    } as never);
    renderBuilder();

    const selectA = screen.getByLabelText(/equipe a/i);
    await within(selectA).findByText("Equipe A");
    await userEvent.selectOptions(selectA, "eq-a");
    await userEvent.selectOptions(screen.getByLabelText(/equipe b/i), "__BYE__");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        expect.objectContaining({ body: { equipe_a_id: "eq-a", equipe_b_id: null } }),
      ),
    );
  });

  it("mostra a mensagem de erro quando o backend recusa", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "EQUIPE_JA_TEM_PARTIDA", mensagem: "Ja tem partida." } },
    } as never);
    renderBuilder();

    const selectA = screen.getByLabelText(/equipe a/i);
    await within(selectA).findByText("Equipe A");
    await userEvent.selectOptions(selectA, "eq-a");
    await userEvent.selectOptions(screen.getByLabelText(/equipe b/i), "eq-b");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    expect(await screen.findByText(/ocorreu um erro inesperado/i)).toBeInTheDocument();
  });

  it("equipe que ja jogou fase de grupos (TODOS_CONTRA_TODOS) aparece elegivel pro mata-mata", async () => {
    // Nivel 2 passou pela fase de grupos na rodada 1 (chave, TODOS_CONTRA_TODOS)
    // -- eq-a e eq-b ja tem partida ali, mas isso NAO deve bloquear elas pro
    // mata-mata: a rodada-alvo bate pra rodada 2 (nova, ainda vazia).
    vi.mocked(api.GET).mockImplementation(async (path: unknown, opts?: unknown) => {
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-a", nome: "Equipe A", nivel: 2, ativo: true },
              { id: "eq-b", nome: "Equipe B", nivel: 2, ativo: true },
              { id: "eq-c", nome: "Equipe C", nivel: 2, ativo: true },
            ],
            total: 3,
            page: 1,
            size: 1000,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return {
          data: {
            itens: [
              { equipe_id: "eq-a", modalidade_id: "mod-1" },
              { equipe_id: "eq-b", modalidade_id: "mod-1" },
              { equipe_id: "eq-c", modalidade_id: "mod-1" },
            ],
            total: 3,
            page: 1,
            size: 1000,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: {
            itens: [
              { id: "r1", numero: 1 },
              { id: "r2", numero: 2 },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        const rodadaId = (opts as { params?: { path?: { rodada_id?: string } } })?.params?.path
          ?.rodada_id;
        if (rodadaId === "r1") {
          return {
            data: [
              {
                id: "p-grupo",
                equipe_a_id: "eq-a",
                equipe_b_id: "eq-b",
                nivel: 2,
                status: "ENCERRADA",
                formato_chaveamento: "TODOS_CONTRA_TODOS",
              },
            ],
            error: undefined,
          } as never;
        }
        return { data: [], error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });
    renderBuilder();

    const selectA = screen.getByLabelText(/equipe a/i);
    await within(selectA).findByText("Equipe A");
    expect(within(selectA).getByText("Equipe B")).toBeInTheDocument();
    expect(within(selectA).getByText("Equipe C")).toBeInTheDocument();
  });

  it("trocar de nivel mostra as equipes daquele nivel", async () => {
    mockDados();
    renderBuilder();

    await within(screen.getByLabelText(/equipe a/i)).findByText("Equipe A");
    await userEvent.selectOptions(await screen.findByLabelText(/^nível$/i), "3");

    const selectA = screen.getByLabelText(/equipe a/i);
    await within(selectA).findByText("Equipe D");
    expect(within(selectA).queryByText("Equipe A")).not.toBeInTheDocument();
  });
});
