import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RodadaListPage } from "./RodadaListPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/rodadas"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas"
            element={<RodadaListPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockGet(rodadas: unknown[]) {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return {
        data: { id: "mod-1", nome: "Sumo de Robos", qtd_rodadas: 3 },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/rodadas") {
      return {
        data: { itens: rodadas, total: rodadas.length, page: 1, size: 100 },
        error: undefined,
      } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RodadaListPage", () => {
  it("mostra um slot por numero de rodada da modalidade", async () => {
    mockGet([]);

    renderPage();

    expect(await screen.findByText(/rodada 1/i)).toBeInTheDocument();
    expect(screen.getByText(/rodada 2/i)).toBeInTheDocument();
    expect(screen.getByText(/rodada 3/i)).toBeInTheDocument();
  });

  it("mostra o horario de uma rodada ja criada", async () => {
    mockGet([
      {
        id: "rod1",
        modalidade_id: "mod-1",
        numero: 1,
        modo_horario: "MANUAL",
        horario_inicio: "2026-03-10T09:00:00Z",
        status: "AGENDADA",
      },
    ]);

    renderPage();

    const linha = (await screen.findByText(/rodada 1/i)).closest("li")!;
    expect(within(linha).getByText(/10\/03\/2026/)).toBeInTheDocument();
  });

  it("nao mostra mais o campo de status manual da rodada", async () => {
    mockGet([
      {
        id: "rod1",
        modalidade_id: "mod-1",
        numero: 1,
        modo_horario: "MANUAL",
        horario_inicio: "2026-03-10T09:00:00Z",
        status: "AGENDADA",
      },
    ]);

    renderPage();

    const linha = (await screen.findByText(/rodada 1/i)).closest("li")!;
    expect(within(linha).queryByLabelText(/status/i)).not.toBeInTheDocument();
  });

  it("linka para lancar notas numa rodada ja criada", async () => {
    mockGet([
      {
        id: "rod1",
        modalidade_id: "mod-1",
        numero: 1,
        modo_horario: "MANUAL",
        horario_inicio: "2026-03-10T09:00:00Z",
        status: "AGENDADA",
      },
    ]);

    renderPage();

    const linha = (await screen.findByText(/rodada 1/i)).closest("li")!;
    const link = within(linha).getByRole("link", { name: /lancar notas/i });
    expect(link).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/rod1/lancamentos/novo",
    );
  });

  it("linka para as fichas enviadas numa rodada ja criada", async () => {
    mockGet([
      {
        id: "rod1",
        modalidade_id: "mod-1",
        numero: 1,
        modo_horario: "MANUAL",
        horario_inicio: "2026-03-10T09:00:00Z",
        status: "AGENDADA",
      },
    ]);

    renderPage();

    const linha = (await screen.findByText(/rodada 1/i)).closest("li")!;
    const link = within(linha).getByRole("link", { name: /ver fichas enviadas/i });
    expect(link).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/rod1/submissoes",
    );
  });

  it("cria uma rodada manual informando o horario", async () => {
    mockGet([]);
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        id: "rod-nova",
        modalidade_id: "mod-1",
        numero: 1,
        modo_horario: "MANUAL",
        horario_inicio: "2026-03-10T09:00:00Z",
        status: "AGENDADA",
      },
      error: undefined,
    } as never);

    renderPage();

    const linha = (await screen.findByText(/rodada 1/i)).closest("li")!;
    await userEvent.click(within(linha).getByRole("button", { name: /criar rodada/i }));
    await userEvent.type(within(linha).getByLabelText(/horario de inicio/i), "2026-03-10T09:00");
    await userEvent.click(within(linha).getByRole("button", { name: /salvar/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/rodadas",
        expect.objectContaining({
          body: expect.objectContaining({ modalidade_id: "mod-1", numero: 1, modo_horario: "MANUAL" }),
        }),
      ),
    );
  });

  it("nao envia rodada manual sem horario, mostra erro antes de chamar a API", async () => {
    mockGet([]);

    renderPage();

    const linha = (await screen.findByText(/rodada 1/i)).closest("li")!;
    await userEvent.click(within(linha).getByRole("button", { name: /criar rodada/i }));
    // modo_horario ja comeca em MANUAL por padrao; nao preenche o horario.
    await userEvent.click(within(linha).getByRole("button", { name: /salvar/i }));

    expect(await within(linha).findByText(/informe o hor[aá]rio/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("gera todas as rodadas faltantes de uma vez", async () => {
    mockGet([]);
    vi.mocked(api.POST).mockResolvedValue({
      data: [
        { id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" },
        { id: "r2", modalidade_id: "mod-1", numero: 2, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" },
        { id: "r3", modalidade_id: "mod-1", numero: 3, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" },
      ],
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /gerar rodadas/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/rodadas/gerar",
        expect.objectContaining({ body: { modalidade_id: "mod-1" } }),
      ),
    );
  });

  function mockGetChaveamento(
    rodadas: unknown[],
    partidasPorRodada: Record<string, unknown[]>,
    chaves: unknown[] = [],
  ) {
    vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: {
            id: "mod-1",
            nome: "Combate",
            qtd_rodadas: 3,
            tipo_disputa: "CONFRONTO",
            formato_chaveamento: "MATA_MATA",
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: { itens: rodadas, total: rodadas.length, page: 1, size: 200 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        const params = opts as { params: { path: { rodada_id: string } } };
        const rodadaId = params.params.path.rodada_id;
        const partidas = (partidasPorRodada[rodadaId] ?? []) as Record<string, unknown>[];
        return {
          data: partidas.map((p) => ({ formato_chaveamento: "MATA_MATA", ...p })),
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}/chaves") {
        return { data: chaves, error: undefined } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe A", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe B", nivel: 1, ativo: true },
              { id: "eq-3", nome: "Equipe C", nivel: 1, ativo: true },
              { id: "eq-4", nome: "Equipe D", nivel: 1, ativo: true },
            ],
            total: 4,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });
  }

  it("modalidade de confronto nao mostra mais 'Gerar chaveamento' (removido do front; so fase de grupos ou manual)", async () => {
    mockGetChaveamento([], {});

    renderPage();

    expect(
      await screen.findByRole("button", { name: /montar chaveamento manual/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^gerar chaveamento$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^gerar rodadas$/i })).not.toBeInTheDocument();
  });

  it("modalidade combate (formato automatico) tambem mostra 'Montar chaveamento manual'", async () => {
    mockGetChaveamento([], {});

    renderPage();

    expect(
      await screen.findByRole("button", { name: /montar chaveamento manual/i }),
    ).toBeInTheDocument();
  });

  it("todos-contra-todos tambem mostra 'Montar chaveamento manual' (todo combate e montado na mao)", async () => {
    mockGetTodosContraTodos([], {});

    renderPage();

    expect(
      await screen.findByRole("button", { name: /montar chaveamento manual/i }),
    ).toBeInTheDocument();
  });

  it("'Montar chaveamento manual' continua visivel mesmo com rodada 1 ja existindo (nivel montado na mao, outro pendente do automatico)", async () => {
    mockGetChaveamento(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      { r1: [{ id: "p1", equipe_a_id: "eq-1", equipe_b_id: "eq-2", vencedor_id: null, status: "AGENDADA", nivel: 2 }] },
    );

    renderPage();

    expect(
      await screen.findByRole("button", { name: /montar chaveamento manual/i }),
    ).toBeInTheDocument();
  });

  it("clicar em 'Montar chaveamento manual' abre o construtor de partida por partida", async () => {
    mockGetChaveamento([], {});

    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: /montar chaveamento manual/i }),
    );

    expect(
      await screen.findByRole("dialog", { name: /montar chaveamento manual/i }),
    ).toBeInTheDocument();
  });

  it("modalidade combate (formato automatico) tambem mostra 'Fase de Grupos'", async () => {
    mockGetChaveamento([], {});

    renderPage();

    expect(await screen.findByRole("button", { name: /^fase de grupos$/i })).toBeInTheDocument();
  });

  it("todos-contra-todos tambem mostra 'Fase de Grupos'", async () => {
    mockGetTodosContraTodos([], {});

    renderPage();

    expect(await screen.findByRole("button", { name: /^fase de grupos$/i })).toBeInTheDocument();
  });

  it("partida de fase de grupos mostra o nome da chave, pra ficar facil de ler quem e de qual grupo", async () => {
    mockGetChaveamento(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            status: "AGENDADA",
            nivel: 1,
            formato_chaveamento: "TODOS_CONTRA_TODOS",
            chave_id: "chave-a",
          },
          {
            id: "p2",
            equipe_a_id: "eq-3",
            equipe_b_id: "eq-4",
            vencedor_id: null,
            status: "AGENDADA",
            nivel: 1,
            formato_chaveamento: "TODOS_CONTRA_TODOS",
            chave_id: "chave-b",
          },
        ],
      },
      [
        { id: "chave-a", modalidade_id: "mod-1", nivel: 1, nome: "Chave A", equipe_ids: ["eq-1", "eq-2"] },
        { id: "chave-b", modalidade_id: "mod-1", nivel: 1, nome: "Chave B", equipe_ids: ["eq-3", "eq-4"] },
      ],
    );

    renderPage();

    expect(await screen.findByText("Chave A")).toBeInTheDocument();
    expect(screen.getByText("Chave B")).toBeInTheDocument();
    // As duas equipes da Chave A aparecem dentro da secao dela, nao da B.
    const secaoA = screen.getByText("Chave A").closest("div")!;
    expect(within(secaoA).getByText(/equipe a vs equipe b/i)).toBeInTheDocument();
  });

  it("clicar em 'Fase de Grupos' abre o construtor de chaves", async () => {
    mockGetChaveamento([], {});

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /^fase de grupos$/i }));

    expect(
      await screen.findByRole("dialog", { name: /montar fase de grupos/i }),
    ).toBeInTheDocument();
  });

  it("chaveamento ja gerado mostra as partidas de cada rodada com o vencedor quando decidido", async () => {
    mockGetChaveamento(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-2",
            status: "ENCERRADA",
          },
        ],
      },
    );

    renderPage();

    expect(await screen.findByText(/Equipe A.*Equipe B/)).toBeInTheDocument();
    expect(await screen.findByText(/Vencedor: Equipe B/)).toBeInTheDocument();
  });

  it("linka para as fichas enviadas numa rodada de chaveamento", async () => {
    mockGetChaveamento(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      { r1: [] },
    );

    renderPage();

    const link = await screen.findByRole("link", { name: /ver fichas enviadas/i });
    expect(link).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/r1/submissoes",
    );
  });

  it("linka a partida pendente do chaveamento direto pro PartidaScorerPage", async () => {
    mockGetChaveamento(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            status: "AGENDADA",
          },
        ],
      },
    );

    renderPage();

    const link = await screen.findByRole("link", { name: /pontuar/i });
    expect(link).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/r1/partidas/p1/pontuar",
    );
  });

  it("nao adivinha campeao nem nome de fase (final/semifinal): chaveamento e montado na mao", async () => {
    mockGetChaveamento(
      [
        { id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" },
        { id: "r2", modalidade_id: "mod-1", numero: 2, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" },
      ],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-1",
            status: "ENCERRADA",
            nivel: 1,
            formato_chaveamento: "MATA_MATA",
          },
        ],
        r2: [
          {
            id: "p2",
            rodada_id: "r2",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-2",
            status: "ENCERRADA",
            nivel: 1,
            formato_chaveamento: "MATA_MATA",
          },
        ],
      },
    );

    renderPage();

    // Pedido do coordenador (14/10/2026): a rodada 2 de um chaveamento montado
    // na mao pode ser a final ou uma semifinal incompleta -- o sistema nao
    // sabe, entao nao chuta. Quem venceu fica no card e no ranking.
    await screen.findByText(/rodada 2/i);
    expect(screen.queryByText(/campe[aã]o/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/final/i)).not.toBeInTheDocument();
  });

  it("nao mostra o link generico 'Lancar notas' na visao de chaveamento (so o Pontuar por partida)", async () => {
    mockGetChaveamento(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            status: "AGENDADA",
          },
        ],
      },
    );

    renderPage();

    await screen.findByText(/Equipe A.*Equipe B/);
    expect(screen.queryByRole("link", { name: /^lancar notas$/i })).not.toBeInTheDocument();
  });

  it("partida ja decidida do chaveamento nao mostra link de pontuar", async () => {
    mockGetChaveamento(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-2",
            status: "ENCERRADA",
          },
        ],
      },
    );

    renderPage();

    await screen.findByText(/Vencedor: Equipe B/);
    expect(screen.queryByRole("link", { name: /pontuar/i })).not.toBeInTheDocument();
  });

  function mockGetTodosContraTodos(rodadas: unknown[], partidasPorRodada: Record<string, unknown[]>) {
    vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: {
            id: "mod-1",
            nome: "Cabo de Guerra",
            qtd_rodadas: 3,
            tipo_disputa: "CONFRONTO",
            formato_chaveamento: "TODOS_CONTRA_TODOS",
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: { itens: rodadas, total: rodadas.length, page: 1, size: 200 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        const params = opts as { params: { path: { rodada_id: string } } };
        const rodadaId = params.params.path.rodada_id;
        const partidas = (partidasPorRodada[rodadaId] ?? []) as Record<string, unknown>[];
        return {
          data: partidas.map((p) => ({ formato_chaveamento: "TODOS_CONTRA_TODOS", ...p })),
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe A", nivel: 1, ativo: true },
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
  }

  it("modalidade de confronto todos-contra-todos nao tem nenhum botao de geracao automatica", async () => {
    mockGetTodosContraTodos([], {});

    renderPage();

    await screen.findByRole("heading", { name: /^rodadas de/i });
    expect(screen.queryByRole("button", { name: /^gerar chaveamento$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^gerar rodadas$/i })).not.toBeInTheDocument();
  });

  it("todos-contra-todos com rodada gerada mostra as partidas com link Pontuar, nao 'Lancar notas'", async () => {
    mockGetTodosContraTodos(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            status: "AGENDADA",
          },
        ],
      },
    );

    renderPage();

    expect(await screen.findByText(/Equipe A.*Equipe B/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /pontuar/i });
    expect(link).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/r1/partidas/p1/pontuar",
    );
    expect(screen.queryByRole("link", { name: /^lancar notas$/i })).not.toBeInTheDocument();
  });

  it("todos-contra-todos com partida decidida mostra o vencedor sem badge de campeao/fase", async () => {
    mockGetTodosContraTodos(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-2",
            status: "ENCERRADA",
          },
        ],
      },
    );

    renderPage();

    expect(await screen.findByText(/Vencedor: Equipe B/)).toBeInTheDocument();
    expect(screen.queryByText(/campe[aã]o/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/final|semifinal|quartas|oitavas/i)).not.toBeInTheDocument();
  });

  it("todos-contra-todos com partida empatada mostra 'Empate'", async () => {
    mockGetTodosContraTodos(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      {
        r1: [
          {
            id: "p1",
            rodada_id: "r1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            status: "EMPATADA",
          },
        ],
      },
    );

    renderPage();

    expect(await screen.findByText(/^empate$/i)).toBeInTheDocument();
  });

  it("linka para as fichas enviadas numa rodada de todos-contra-todos", async () => {
    mockGetTodosContraTodos(
      [{ id: "r1", modalidade_id: "mod-1", numero: 1, modo_horario: "AUTOMATICO", horario_inicio: null, status: "AGENDADA" }],
      { r1: [] },
    );

    renderPage();

    const link = await screen.findByRole("link", { name: /ver fichas enviadas/i });
    expect(link).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/r1/submissoes",
    );
  });

});
