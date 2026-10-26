import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ChaveamentoManualBuilder } from "./ChaveamentoManualBuilder";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderBuilder(onFechar = vi.fn(), comoPagina = false) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChaveamentoManualBuilder
        modalidadeId="mod-1"
        onFechar={comoPagina ? undefined : onFechar}
        comoPagina={comoPagina}
      />
    </QueryClientProvider>,
  );
}

// Equipes viraram botoes (toque na A, toque na B): a lista suspensa nativa
// fechava sozinha dentro da janela com rolagem.
function grupoEquipes() {
  return screen.getByRole("group", { name: /equipes disponíveis/i });
}

function botaoEquipe(nome: string) {
  return within(grupoEquipes()).queryByRole("button", { name: new RegExp(`^${nome}`) });
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
            { id: "eq-x", nome: "Equipe Ausente", nivel: 2, ativo: true, presente: false },
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
            { equipe_id: "eq-x", modalidade_id: "mod-1" },
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

async function escolherEquipes(a: string, b: string) {
  await within(grupoEquipes()).findByRole("button", { name: new RegExp(`^${a}`) });
  await userEvent.click(botaoEquipe(a)!);
  if (b === "BYE") {
    await userEvent.click(screen.getByRole("button", { name: /bye/i }));
  } else {
    await userEvent.click(botaoEquipe(b)!);
  }
}

const PARTIDA_A_X_B_RODADA_1 = {
  id: "p1",
  equipe_a_id: "eq-a",
  equipe_b_id: "eq-b",
  nivel: 2,
  status: "AGENDADA",
  formato_chaveamento: "TODOS_CONTRA_TODOS",
};

describe("ChaveamentoManualBuilder", () => {
  it("mostra as equipes elegiveis do nivel selecionado como botoes", async () => {
    mockDados();
    renderBuilder();

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe A/ });
    expect(botaoEquipe("Equipe B")).toBeInTheDocument();
    expect(botaoEquipe("Equipe D")).not.toBeInTheDocument();
  });

  it("equipe marcada como ausente nao aparece nas opcoes", async () => {
    mockDados();
    renderBuilder();

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe A/ });
    expect(botaoEquipe("Equipe Ausente")).not.toBeInTheDocument();
  });

  it("primeiro toque vira a equipe A, segundo vira a equipe B", async () => {
    mockDados();
    renderBuilder();

    await escolherEquipes("Equipe C", "Equipe A");

    expect(screen.getByTestId("lado-a")).toHaveTextContent("Equipe C");
    expect(screen.getByTestId("lado-b")).toHaveTextContent("Equipe A");
    expect(botaoEquipe("Equipe C")).toHaveAttribute("aria-pressed", "true");
  });

  it("tocar de novo numa equipe escolhida desmarca", async () => {
    mockDados();
    renderBuilder();

    await escolherEquipes("Equipe A", "Equipe B");
    await userEvent.click(botaoEquipe("Equipe A")!);

    expect(screen.getByTestId("lado-a")).not.toHaveTextContent("Equipe A");
    expect(botaoEquipe("Equipe A")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /salvar confronto/i })).toBeDisabled();
  });

  it("comeca na ultima rodada que ja existe", async () => {
    mockDados([PARTIDA_A_X_B_RODADA_1]);
    renderBuilder();

    await waitFor(() => expect(screen.getByLabelText(/^rodada$/i)).toHaveValue(1));
  });

  it("equipe que ja tem partida na rodada escolhida some das opcoes e aparece na lista", async () => {
    mockDados([PARTIDA_A_X_B_RODADA_1]);
    renderBuilder();

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe C/ });
    await waitFor(() => expect(botaoEquipe("Equipe A")).not.toBeInTheDocument());
    expect(botaoEquipe("Equipe B")).not.toBeInTheDocument();
    expect(await screen.findByText(/equipe a.*x.*equipe b/i)).toBeInTheDocument();
  });

  it("em outra rodada a mesma equipe volta a ser elegivel (semifinal/final na mao)", async () => {
    mockDados([PARTIDA_A_X_B_RODADA_1]);
    renderBuilder();

    const rodada = screen.getByLabelText(/^rodada$/i);
    await waitFor(() => expect(rodada).toHaveValue(1));
    await userEvent.clear(rodada);
    await userEvent.type(rodada, "2");

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe A/ });
    expect(botaoEquipe("Equipe B")).toBeInTheDocument();
    expect(screen.queryByText(/equipe a.*x.*equipe b/i)).not.toBeInTheDocument();
  });

  it("salva confronto eliminatorio com a rodada escolhida", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "p-nova" }, error: undefined } as never);
    renderBuilder();

    await escolherEquipes("Equipe A", "Equipe B");
    await userEvent.selectOptions(screen.getByLabelText(/^tipo$/i), "MATA_MATA");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        expect.objectContaining({
          params: { path: { modalidade_id: "mod-1" } },
          body: {
            equipe_a_id: "eq-a",
            equipe_b_id: "eq-b",
            rodada_numero: 1,
            formato_chaveamento: "MATA_MATA",
          },
        }),
      ),
    );
  });

  it("salva confronto de fase de grupos", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "p-nova" }, error: undefined } as never);
    renderBuilder();

    await userEvent.selectOptions(screen.getByLabelText(/^tipo$/i), "TODOS_CONTRA_TODOS");
    await escolherEquipes("Equipe A", "Equipe C");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        expect.objectContaining({
          body: expect.objectContaining({ formato_chaveamento: "TODOS_CONTRA_TODOS" }),
        }),
      ),
    );
  });

  it("fase de grupos nao oferece bye", async () => {
    mockDados();
    renderBuilder();

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe A/ });
    await userEvent.selectOptions(screen.getByLabelText(/^tipo$/i), "TODOS_CONTRA_TODOS");

    expect(screen.queryByRole("button", { name: /bye/i })).not.toBeInTheDocument();
  });

  it("salva um bye em confronto eliminatorio", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "p-nova" }, error: undefined } as never);
    renderBuilder();

    await userEvent.selectOptions(screen.getByLabelText(/^tipo$/i), "MATA_MATA");
    await escolherEquipes("Equipe A", "BYE");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
        expect.objectContaining({
          body: expect.objectContaining({ equipe_a_id: "eq-a", equipe_b_id: null }),
        }),
      ),
    );
  });

  it("depois de salvar limpa a escolha pra montar o proximo", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "p-nova" }, error: undefined } as never);
    renderBuilder();

    await escolherEquipes("Equipe A", "Equipe B");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    await waitFor(() => expect(screen.getByTestId("lado-a")).not.toHaveTextContent("Equipe A"));
    expect(screen.getByTestId("lado-b")).not.toHaveTextContent("Equipe B");
  });

  it("mostra a mensagem de erro quando o backend recusa", async () => {
    mockDados();
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "EQUIPE_JA_TEM_PARTIDA", mensagem: "Ja tem partida." } },
    } as never);
    renderBuilder();

    await escolherEquipes("Equipe A", "Equipe B");
    await userEvent.click(screen.getByRole("button", { name: /salvar confronto/i }));

    expect(await screen.findByText(/ocorreu um erro inesperado/i)).toBeInTheDocument();
  });

  it("trocar de nivel mostra as equipes daquele nivel", async () => {
    mockDados();
    renderBuilder();

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe A/ });
    const niveis = screen.getByRole("group", { name: /^nível$/i });
    expect(within(niveis).getByRole("button", { name: "Nível 2" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await userEvent.click(within(niveis).getByRole("button", { name: "Nível 3" }));

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe D/ });
    expect(botaoEquipe("Equipe A")).not.toBeInTheDocument();
  });

  it("mostra o nivel mesmo quando a modalidade so tem equipe de um nivel", async () => {
    mockDados();
    vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
      if (path === "/api/v1/equipes") {
        return { data: { itens: [{ id: "eq-d", nome: "Equipe D", nivel: 3 }] } } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return { data: { itens: [{ equipe_id: "eq-d", modalidade_id: "mod-1" }] } } as never;
      }
      return { data: { itens: [] } } as never;
    });
    renderBuilder();

    const niveis = await screen.findByRole("group", { name: /^nível$/i });
    expect(within(niveis).getByRole("button", { name: "Nível 3" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("arrastar a equipe pro quadro da equipe B escolhe ela como B", async () => {
    mockDados();
    renderBuilder();

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe C/ });
    fireEvent.dragStart(botaoEquipe("Equipe C")!, { dataTransfer: { setData: vi.fn() } });
    fireEvent.dragOver(screen.getByTestId("slot-b"));
    fireEvent.drop(screen.getByTestId("slot-b"));

    expect(screen.getByTestId("lado-b")).toHaveTextContent("Equipe C");
    expect(screen.getByTestId("lado-a")).toHaveTextContent("—");
  });

  it("arrastar pra um quadro ja ocupado troca a equipe dele", async () => {
    mockDados();
    renderBuilder();

    await escolherEquipes("Equipe A", "Equipe B");
    fireEvent.dragStart(botaoEquipe("Equipe C")!, { dataTransfer: { setData: vi.fn() } });
    fireEvent.drop(screen.getByTestId("slot-a"));

    expect(screen.getByTestId("lado-a")).toHaveTextContent("Equipe C");
    expect(screen.getByTestId("lado-b")).toHaveTextContent("Equipe B");
  });

  it("arrastar a equipe B pro quadro A troca de lado sem repetir", async () => {
    mockDados();
    renderBuilder();

    await escolherEquipes("Equipe A", "Equipe B");
    fireEvent.dragStart(botaoEquipe("Equipe B")!, { dataTransfer: { setData: vi.fn() } });
    fireEvent.drop(screen.getByTestId("slot-a"));

    expect(screen.getByTestId("lado-a")).toHaveTextContent("Equipe B");
    expect(screen.getByTestId("lado-b")).toHaveTextContent("—");
  });

  it("como pagina, nao abre janela por cima nem tem botao de fechar", async () => {
    mockDados();
    renderBuilder(vi.fn(), true);

    await within(grupoEquipes()).findByRole("button", { name: /^Equipe A/ });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^fechar$/i })).not.toBeInTheDocument();
  });

  it("como janela, o botao fechar chama onFechar", async () => {
    mockDados();
    const onFechar = vi.fn();
    renderBuilder(onFechar);

    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /^fechar$/i }));
    expect(onFechar).toHaveBeenCalled();
  });
});
