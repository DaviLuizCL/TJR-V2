import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PontuarCombatePage } from "./PontuarCombatePage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(caminho = "/eventos/evt-1/modalidades/mod-1/pontuar") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[caminho]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/pontuar"
            element={<PontuarCombatePage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

interface MockConfig {
  rodadas?: { id: string; numero: number }[];
  partidasPorRodada?: Record<string, unknown[]>;
  equipes?: unknown[];
  formatoChaveamento?: string | null;
}

function mockGet(cfg: MockConfig = {}) {
  const rodadas = cfg.rodadas ?? [{ id: "rod-1", modalidade_id: "mod-1", numero: 1 }];
  const equipes = cfg.equipes ?? [
    { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
    { id: "eq-2", nome: "Equipe Y", nivel: 1, ativo: true },
  ];

  vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return {
        data: {
          id: "mod-1",
          nome: "Sumo de Robos",
          tipo_disputa: "CONFRONTO",
          formato_chaveamento: cfg.formatoChaveamento ?? "MATA_MATA",
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
    if (path === "/api/v1/equipes") {
      return {
        data: { itens: equipes, total: equipes.length, page: 1, size: 200 },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
      const params = opts as { params: { path: { rodada_id: string } } };
      const rodadaId = params.params.path.rodada_id;
      return { data: cfg.partidasPorRodada?.[rodadaId] ?? [], error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PontuarCombatePage", () => {
  it("mostra partida pendente como card clicavel linkando pro formulario com a partida na url", async () => {
    mockGet({
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
        ],
      },
    });

    renderPage();

    const card = (await screen.findByText(/equipe x/i)).closest("a")!;
    expect(card).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/partidas/par-1/pontuar",
    );
    expect(within(card).getByText(/equipe y/i)).toBeInTheDocument();
  });

  it("partida encerrada nao fica clicavel, mostra vencedor em verde e perdedor em vermelho, com rotulo de texto", async () => {
    mockGet({
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-1",
            nivel: 1,
            status: "ENCERRADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
        ],
      },
    });

    renderPage();

    const nomeVencedor = await screen.findByText(/^equipe x$/i);
    expect(nomeVencedor.closest("a")).toBeNull();
    expect(nomeVencedor).toHaveClass("text-emerald-700");

    const nomePerdedor = screen.getByText(/^equipe y$/i);
    expect(nomePerdedor).toHaveClass("text-red-700");

    expect(screen.getByText(/vencedor: equipe x/i)).toBeInTheDocument();
  });

  it("partida empatada nao fica clicavel e mostra rotulo de empate sem cor de vencedor", async () => {
    mockGet({
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "EMPATADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
        ],
      },
    });

    renderPage();

    const nomeA = await screen.findByText(/equipe x/i);
    expect(nomeA.closest("a")).toBeNull();
    expect(nomeA).not.toHaveClass("text-emerald-700");
    expect(nomeA).not.toHaveClass("text-red-700");
    expect(screen.getByText(/empate/i)).toBeInTheDocument();
  });

  it("bye mostra a equipe vencedora em verde e (bye) do outro lado, sem clique", async () => {
    mockGet({
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: null,
            vencedor_id: "eq-1",
            nivel: 1,
            status: "ENCERRADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
        ],
      },
    });

    renderPage();

    const nomeA = await screen.findByText(/^equipe x$/i);
    expect(nomeA.closest("a")).toBeNull();
    expect(nomeA).toHaveClass("text-emerald-700");
    expect(screen.getByText(/\(bye\)/i)).toBeInTheDocument();
    expect(screen.getByText(/vencedor: equipe x/i)).toBeInTheDocument();
  });

  it("dentro da mesma fase, ordena as partidas por nivel e depois por criacao", async () => {
    mockGet({
      formatoChaveamento: "TODOS_CONTRA_TODOS", // 1 fase so, sem interferencia de ordenacao entre rodadas
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-nivel-2",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 2,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
          {
            id: "par-nivel-1-b",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:02Z",
          },
          {
            id: "par-nivel-1-a",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:01Z",
          },
        ],
      },
    });

    renderPage();

    await screen.findAllByText(/equipe x/i);
    const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href")?.includes("/partidas/"));
    const ordemIds = links.map((a) => a.getAttribute("href")!.match(/\/partidas\/([^/]+)\/pontuar/)?.[1]);
    expect(ordemIds).toEqual(["par-nivel-1-a", "par-nivel-1-b", "par-nivel-2"]);
  });

  it("filtra as partidas por nivel", async () => {
    mockGet({
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-nivel-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
          {
            id: "par-nivel-2",
            rodada_id: "rod-1",
            equipe_a_id: "eq-3",
            equipe_b_id: "eq-4",
            vencedor_id: null,
            nivel: 2,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:01Z",
          },
        ],
      },
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 1, ativo: true },
        { id: "eq-3", nome: "Equipe Z", nivel: 2, ativo: true },
        { id: "eq-4", nome: "Equipe W", nivel: 2, ativo: true },
      ],
    });

    renderPage();

    await screen.findByText(/equipe x/i);
    expect(screen.getByText(/equipe z/i)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/filtrar por nivel/i), "1");

    expect(screen.getByText(/equipe x/i)).toBeInTheDocument();
    expect(screen.queryByText(/equipe z/i)).not.toBeInTheDocument();
  });

  it("nao mostra filtro de nivel quando so ha 1 nivel entre as partidas", async () => {
    mockGet({
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
        ],
      },
    });

    renderPage();

    await screen.findByText(/equipe x/i);
    expect(screen.queryByLabelText(/filtrar por nivel/i)).not.toBeInTheDocument();
  });

  it("agrupa as partidas em secoes de fase (semifinal, final) num bracket de 4 equipes", async () => {
    mockGet({
      rodadas: [
        { id: "rod-1", numero: 1 },
        { id: "rod-2", numero: 2 },
      ],
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-semi-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-1",
            nivel: 1,
            status: "ENCERRADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
          {
            id: "par-semi-2",
            rodada_id: "rod-1",
            equipe_a_id: "eq-3",
            equipe_b_id: "eq-4",
            vencedor_id: "eq-3",
            nivel: 1,
            status: "ENCERRADA",
            criado_em: "2026-08-05T10:00:01Z",
          },
        ],
        "rod-2": [
          {
            id: "par-final",
            rodada_id: "rod-2",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-3",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T11:00:00Z",
          },
        ],
      },
    });

    renderPage();

    const semifinal = await screen.findByRole("heading", { name: /semifinal/i });
    const final = await screen.findByRole("heading", { name: /^final$/i });

    // rodada mais nova (final, rodada 2) fica em cima da mais antiga (semifinal, rodada 1)
    expect(
      final.compareDocumentPosition(semifinal) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    const secaoSemifinal = semifinal.closest("section")!;
    expect(within(secaoSemifinal).getAllByRole("listitem")).toHaveLength(2);

    const secaoFinal = final.closest("section")!;
    expect(within(secaoFinal).getAllByRole("listitem")).toHaveLength(1);
  });

  it("secao com nome de fase (oitavas) fica acima de uma secao 'Rodada N' generica mais antiga, mesmo com escalas de ordenacao diferentes", async () => {
    // Bracket de 20 equipes: precisa de 5 rodadas (ceil(log2(20))). A rodada
    // 1 e grande demais pra ter nome (cai no fallback "Rodada 1"), mas a
    // rodada 2 ja tem nome ("Oitavas de Final"). Regressao do bug onde as
    // duas escalas de ordenacao (fallback vs nomeada) nao eram compativeis:
    // "Oitavas" (uma rodada mais nova) acabava caindo depois de "Rodada 1"
    // (mais antiga) na tela.
    const partidasRodada1 = Array.from({ length: 10 }, (_, i) => ({
      id: `par-r1-${i}`,
      rodada_id: "rod-1",
      equipe_a_id: `eq-${i * 2}`,
      equipe_b_id: `eq-${i * 2 + 1}`,
      vencedor_id: null,
      nivel: 1,
      status: "AGENDADA",
      criado_em: `2026-08-05T10:00:${String(i).padStart(2, "0")}Z`,
    }));
    mockGet({
      rodadas: [
        { id: "rod-1", numero: 1 },
        { id: "rod-2", numero: 2 },
      ],
      partidasPorRodada: {
        "rod-1": partidasRodada1,
        "rod-2": [
          {
            id: "par-oitavas",
            rodada_id: "rod-2",
            equipe_a_id: "eq-0",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T11:00:00Z",
          },
        ],
      },
    });

    renderPage();

    const oitavas = await screen.findByRole("heading", { name: /oitavas de final/i });
    const rodada1 = await screen.findByRole("heading", { name: /^rodada 1$/i });

    expect(
      oitavas.compareDocumentPosition(rodada1) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("agrupa tudo em 'Fase de Grupos' quando a modalidade e todos-contra-todos", async () => {
    mockGet({
      formatoChaveamento: "TODOS_CONTRA_TODOS",
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
        ],
      },
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: /fase de grupos/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^final$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /semifinal/i })).not.toBeInTheDocument();
  });

  it("mostra as partidas pendentes antes das ja decididas dentro da mesma fase", async () => {
    mockGet({
      formatoChaveamento: "TODOS_CONTRA_TODOS",
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-decidida",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: "eq-1",
            nivel: 1,
            status: "ENCERRADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
          {
            id: "par-pendente",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:01Z",
          },
        ],
      },
    });

    renderPage();

    const secao = (await screen.findByRole("heading", { name: /fase de grupos/i })).closest(
      "section",
    )!;
    const itens = within(secao).getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    expect(within(itens[0]).getByRole("link")).toHaveAttribute(
      "href",
      expect.stringContaining("par-pendente"),
    );
    expect(within(itens[1]).queryByRole("link")).not.toBeInTheDocument();
  });

  it("mostra mensagem quando nao ha nenhuma partida gerada", async () => {
    mockGet({ partidasPorRodada: {} });

    renderPage();

    expect(await screen.findByText(/nenhuma partida/i)).toBeInTheDocument();
  });

  it("abrir a pagina com ?nivel= na url ja vem com esse nivel selecionado no filtro", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 1, ativo: true },
        { id: "eq-3", nome: "Equipe Z", nivel: 2, ativo: true },
        { id: "eq-4", nome: "Equipe W", nivel: 2, ativo: true },
      ],
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
          {
            id: "par-2",
            rodada_id: "rod-1",
            equipe_a_id: "eq-3",
            equipe_b_id: "eq-4",
            vencedor_id: null,
            nivel: 2,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:01Z",
          },
        ],
      },
    });

    renderPage("/eventos/evt-1/modalidades/mod-1/pontuar?nivel=2");

    const select = (await screen.findByLabelText(/filtrar por nivel/i)) as HTMLSelectElement;
    expect(select.value).toBe("2");
    expect(await screen.findByText(/equipe z/i)).toBeInTheDocument();
    expect(screen.queryByText(/equipe x/i)).not.toBeInTheDocument();
  });

  it("escolher um nivel no filtro atualiza a url e o link da partida carrega o nivel junto", async () => {
    mockGet({
      partidasPorRodada: {
        "rod-1": [
          {
            id: "par-1",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 1,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:00Z",
          },
          {
            id: "par-2",
            rodada_id: "rod-1",
            equipe_a_id: "eq-1",
            equipe_b_id: "eq-2",
            vencedor_id: null,
            nivel: 2,
            status: "AGENDADA",
            criado_em: "2026-08-05T10:00:01Z",
          },
        ],
      },
    });

    renderPage();
    await userEvent.selectOptions(await screen.findByLabelText(/filtrar por nivel/i), "1");

    const card = (await screen.findByText(/equipe x/i)).closest("a")!;
    expect(card).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/partidas/par-1/pontuar?nivel=1",
    );
  });
});
