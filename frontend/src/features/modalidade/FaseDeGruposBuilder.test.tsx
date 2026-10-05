import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { FaseDeGruposBuilder } from "./FaseDeGruposBuilder";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderBuilder(onFechar = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <FaseDeGruposBuilder modalidadeId="mod-1" onFechar={onFechar} />
    </QueryClientProvider>,
  );
}

function mockDados(chaves: Record<string, unknown>[] = []) {
  vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
    if (path === "/api/v1/equipes") {
      return {
        data: {
          itens: [
            { id: "eq-a", nome: "Equipe A", nivel: 1, ativo: true },
            { id: "eq-b", nome: "Equipe B", nivel: 1, ativo: true },
            { id: "eq-c", nome: "Equipe C", nivel: 1, ativo: true },
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
    if (path === "/api/v1/modalidades/{modalidade_id}/chaves") {
      return { data: chaves, error: undefined } as never;
    }
    if (path === "/api/v1/chaves/{chave_id}/classificacao") {
      return { data: [], error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FaseDeGruposBuilder", () => {
  it("cria uma chave nova com o nome digitado", async () => {
    mockDados([]);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "chave-1", modalidade_id: "mod-1", nivel: 1, nome: "Chave A", equipe_ids: [] },
      error: undefined,
    } as never);
    renderBuilder();

    await screen.findByText(/nenhuma chave criada ainda/i);
    await userEvent.type(screen.getByLabelText(/nome da nova chave/i), "Chave A");
    await userEvent.click(screen.getByRole("button", { name: /^criar chave$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/chaves",
        expect.objectContaining({
          params: { path: { modalidade_id: "mod-1" } },
          body: { modalidade_id: "mod-1", nivel: 1, nome: "Chave A" },
        }),
      ),
    );
  });

  it("mostra as chaves existentes com suas equipes e permite adicionar outra", async () => {
    mockDados([
      { id: "chave-1", modalidade_id: "mod-1", nivel: 1, nome: "Chave A", equipe_ids: ["eq-a"] },
    ]);
    vi.mocked(api.POST).mockResolvedValue({ data: undefined, error: undefined } as never);
    renderBuilder();

    expect(await screen.findByText("Chave A")).toBeInTheDocument();
    expect(screen.getByText("Equipe A")).toBeInTheDocument();

    const selectAdicionar = screen.getByLabelText(/adicionar equipe na chave a/i);
    // eq-a ja esta na chave, so eq-b e eq-c ficam disponiveis pra adicionar
    expect(within(selectAdicionar).queryByText("Equipe A")).not.toBeInTheDocument();
    expect(within(selectAdicionar).getByText("Equipe B")).toBeInTheDocument();

    await userEvent.selectOptions(selectAdicionar, "eq-b");
    await userEvent.click(screen.getByRole("button", { name: /^adicionar$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/chaves/{chave_id}/equipes",
        expect.objectContaining({
          params: { path: { chave_id: "chave-1" } },
          body: { equipe_id: "eq-b" },
        }),
      ),
    );
  });

  it("remove uma equipe da chave", async () => {
    mockDados([
      { id: "chave-1", modalidade_id: "mod-1", nivel: 1, nome: "Chave A", equipe_ids: ["eq-a"] },
    ]);
    vi.mocked(api.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);
    renderBuilder();

    await screen.findByText("Equipe A");
    await userEvent.click(screen.getByRole("button", { name: /remover/i }));

    await waitFor(() =>
      expect(api.DELETE).toHaveBeenCalledWith(
        "/api/v1/chaves/{chave_id}/equipes/{equipe_id}",
        expect.objectContaining({
          params: { path: { chave_id: "chave-1", equipe_id: "eq-a" } },
        }),
      ),
    );
  });

  it("mostra erro quando o backend recusa adicionar equipe (ja esta em outra chave)", async () => {
    mockDados([
      { id: "chave-1", modalidade_id: "mod-1", nivel: 1, nome: "Chave A", equipe_ids: [] },
    ]);
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "EQUIPE_JA_TEM_CHAVE", mensagem: "Ja esta em outra chave." } },
    } as never);
    renderBuilder();

    const selectAdicionar = await screen.findByLabelText(/adicionar equipe na chave a/i);
    await userEvent.selectOptions(selectAdicionar, "eq-a");
    await userEvent.click(screen.getByRole("button", { name: /^adicionar$/i }));

    expect(await screen.findByText(/ocorreu um erro inesperado/i)).toBeInTheDocument();
  });

  it("mostra a classificacao da chave quando ha partidas decididas", async () => {
    mockDados([
      {
        id: "chave-1",
        modalidade_id: "mod-1",
        nivel: 1,
        nome: "Chave A",
        equipe_ids: ["eq-a", "eq-b"],
      },
    ]);
    vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-a", nome: "Equipe A", nivel: 1, ativo: true },
              { id: "eq-b", nome: "Equipe B", nivel: 1, ativo: true },
            ],
            total: 2,
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
            ],
            total: 2,
            page: 1,
            size: 1000,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}/chaves") {
        return {
          data: [
            {
              id: "chave-1",
              modalidade_id: "mod-1",
              nivel: 1,
              nome: "Chave A",
              equipe_ids: ["eq-a", "eq-b"],
            },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/chaves/{chave_id}/classificacao") {
        return {
          data: [
            { equipe_id: "eq-b", nota_final: 3, vitorias: 1, empates: 0, derrotas: 0, posicao: 1 },
            { equipe_id: "eq-a", nota_final: 0, vitorias: 0, empates: 0, derrotas: 1, posicao: 2 },
          ],
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });
    renderBuilder();

    await screen.findByText("Chave A");
    const classificacao = await screen.findByRole("list", { name: /classificação da chave a/i });
    const linhas = within(classificacao).getAllByRole("listitem");
    expect(linhas[0]).toHaveTextContent(/1º/);
    expect(linhas[0]).toHaveTextContent("Equipe B");
    expect(linhas[1]).toHaveTextContent(/2º/);
    expect(linhas[1]).toHaveTextContent("Equipe A");
  });

  it("atualiza a classificacao depois de adicionar uma equipe (nao fica com cache velho)", async () => {
    // Bug real achado testando ao vivo: adicionar a 2a equipe nao invalidava
    // a query de classificacao, entao a chave ficava mostrando só a 1a
    // equipe pra sempre, mesmo com as duas ja na chave.
    let chamadasClassificacao = 0;
    vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-a", nome: "Equipe A", nivel: 1, ativo: true },
              { id: "eq-b", nome: "Equipe B", nivel: 1, ativo: true },
            ],
            total: 2,
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
            ],
            total: 2,
            page: 1,
            size: 1000,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}/chaves") {
        // 1a leitura: só eq-a na chave. Depois do "adicionar", a lista de
        // chaves já reflete as duas (invalidada por invalidar()).
        const equipeIds = chamadasClassificacao === 0 ? ["eq-a"] : ["eq-a", "eq-b"];
        return {
          data: [
            { id: "chave-1", modalidade_id: "mod-1", nivel: 1, nome: "Chave A", equipe_ids: equipeIds },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/chaves/{chave_id}/classificacao") {
        chamadasClassificacao += 1;
        const itens =
          chamadasClassificacao === 1
            ? [{ equipe_id: "eq-a", nota_final: 0, vitorias: 0, empates: 0, derrotas: 0, posicao: 1 }]
            : [
                { equipe_id: "eq-a", nota_final: 0, vitorias: 0, empates: 0, derrotas: 0, posicao: 1 },
                { equipe_id: "eq-b", nota_final: 0, vitorias: 0, empates: 0, derrotas: 0, posicao: 2 },
              ];
        return { data: itens, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });
    vi.mocked(api.POST).mockResolvedValue({ data: undefined, error: undefined } as never);
    renderBuilder();

    const classificacao = await screen.findByRole("list", { name: /classificação da chave a/i });
    await waitFor(() => expect(within(classificacao).getAllByRole("listitem")).toHaveLength(1));

    await userEvent.selectOptions(screen.getByLabelText(/adicionar equipe na chave a/i), "eq-b");
    await userEvent.click(screen.getByRole("button", { name: /^adicionar$/i }));

    await waitFor(() =>
      expect(within(classificacao).getAllByRole("listitem")).toHaveLength(2),
    );
  });

  it("nao gera confronto sozinho: sem botao de gerar fase de grupos", async () => {
    mockDados([{ id: "ch-1", modalidade_id: "mod-1", nivel: 1, nome: "Chave A", equipe_ids: [] }]);
    renderBuilder();

    await screen.findByText("Chave A");
    expect(screen.queryByRole("button", { name: /gerar fase de grupos/i })).not.toBeInTheDocument();
  });
});
