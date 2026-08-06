import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PartidaScorerPage } from "./PartidaScorerPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: (error: unknown) => {
    const erro = (error as { erro?: { codigo: string; mensagem: string } })?.erro;
    return erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." };
  },
}));

const ROTA = "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/partidas/par-1/pontuar";

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[ROTA]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas/:rodadaId/partidas/:partidaId/pontuar"
            element={<PartidaScorerPage />}
          />
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/pontuar"
            element={<div>TELA DE PONTUAR</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const PARTIDA_BASE = {
  id: "par-1",
  rodada_id: "rod-1",
  equipe_a_id: "eq-1",
  equipe_b_id: "eq-2",
  vencedor_id: null,
  nivel: 1,
  status: "AGENDADA",
};

const EQUIPES = [
  { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
  { id: "eq-2", nome: "Equipe Y", nivel: 1, ativo: true },
];

const FICHA_BOOLEANA = {
  id: "ficha-1",
  grupos: [
    {
      id: "grupo-1",
      nome: "Geral",
      criterios: [
        {
          id: "crit-1",
          nome: "Venceu o combate",
          categoria: "PONTUACAO",
          tipo: "BOOLEANO",
          pontos: 1,
          valores_permitidos: null,
          max_ocorrencias: null,
        },
      ],
    },
  ],
};

const FICHA_ESCALA = {
  id: "ficha-2",
  grupos: [
    {
      id: "grupo-1",
      nome: "Geral",
      criterios: [
        {
          id: "crit-2",
          nome: "Resultado do arrasto",
          categoria: "PONTUACAO",
          tipo: "ESCALA",
          pontos: null,
          valores_permitidos: [0, 1, 2],
          max_ocorrencias: null,
        },
      ],
    },
  ],
};

const FICHA_MULTI = {
  id: "ficha-3",
  grupos: [
    {
      id: "grupo-1",
      nome: "Geral",
      criterios: [
        {
          id: "crit-3",
          nome: "Ataque",
          categoria: "PONTUACAO",
          tipo: "CONTADOR",
          pontos: 10,
          valores_permitidos: null,
          max_ocorrencias: null,
        },
        {
          id: "crit-4",
          nome: "Defesa",
          categoria: "PONTUACAO",
          tipo: "CONTADOR",
          pontos: 5,
          valores_permitidos: null,
          max_ocorrencias: null,
        },
      ],
    },
  ],
};

interface MockConfig {
  partida?: Record<string, unknown>;
  ficha?: typeof FICHA_BOOLEANA | typeof FICHA_ESCALA | typeof FICHA_MULTI;
  tentativasPorRodada?: number;
  lancamentos?: unknown[];
}

function mockGet(cfg: MockConfig = {}) {
  const partida = { ...PARTIDA_BASE, ...cfg.partida };
  const ficha = cfg.ficha ?? FICHA_BOOLEANA;

  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
      return { data: [partida], error: undefined } as never;
    }
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return {
        data: {
          id: "mod-1",
          nome: "Sumo de Robos",
          ficha_unica_entre_niveis: true,
          tentativas_por_rodada: cfg.tentativasPorRodada ?? 3,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/fichas") {
      return {
        data: { itens: [{ id: ficha.id, nivel: null, status: "PUBLICADA" }], total: 1, page: 1, size: 100 },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/fichas/{ficha_id}") {
      return { data: ficha, error: undefined } as never;
    }
    if (path === "/api/v1/equipes") {
      return { data: { itens: EQUIPES, total: 2, page: 1, size: 200 }, error: undefined } as never;
    }
    if (path === "/api/v1/lancamentos") {
      return {
        data: { itens: cfg.lancamentos ?? [], total: (cfg.lancamentos ?? []).length, page: 1, size: 200 },
        error: undefined,
      } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PartidaScorerPage - ficha com um criterio booleano", () => {
  it("mostra os 3 combates com 'defina o vencedor' e um botao neutro por equipe mais empate", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByText(/combate 1/i)).toBeInTheDocument();
    expect(screen.getByText(/combate 2/i)).toBeInTheDocument();
    expect(screen.getByText(/combate 3/i)).toBeInTheDocument();
    expect(screen.getAllByText(/defina o vencedor/i)).toHaveLength(3);

    const botoesEquipeX = screen.getAllByRole("button", { name: /^equipe x$/i });
    expect(botoesEquipeX).toHaveLength(3);
    const botoesEquipeY = screen.getAllByRole("button", { name: /^equipe y$/i });
    expect(botoesEquipeY).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: /^empate$/i })).toHaveLength(3);

    for (const botao of [...botoesEquipeX, ...botoesEquipeY]) {
      expect(botao).not.toHaveClass("text-emerald-800");
      expect(botao).not.toHaveClass("bg-emerald-50");
    }

    expect(screen.queryByLabelText(/^equipe$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^tentativa$/i)).not.toBeInTheDocument();
  });

  it("clicar no nome da Equipe X registra e confirma os dois lancamentos com as ocorrencias certas", async () => {
    mockGet();
    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/lancamentos") {
        const body = (opts as { body: { equipe_id: string } }).body;
        return {
          data: { id: `lanc-${body.equipe_id}`, status: "PENDENTE", total: 0 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        return { data: { id: "lanc-1", status: "CONFIRMADO", total: 0 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    await userEvent.click(within(combate1).getByRole("button", { name: /^equipe x$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({
            equipe_id: "eq-1",
            tentativa: 1,
            partida_id: "par-1",
            itens: [{ criterio_id: "crit-1", ocorrencias: 1 }],
          }),
        }),
      ),
    );
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({
            equipe_id: "eq-2",
            tentativa: 1,
            partida_id: "par-1",
            itens: [{ criterio_id: "crit-1", ocorrencias: 0 }],
          }),
        }),
      ),
    );
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos/{lancamento_id}/confirmar",
        expect.anything(),
      ),
    );
  });

  it("clicar 'Empate' registra os dois lados com ocorrencias 0", async () => {
    mockGet();
    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/lancamentos") {
        const body = (opts as { body: { equipe_id: string } }).body;
        return { data: { id: `lanc-${body.equipe_id}`, status: "PENDENTE", total: 0 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        return { data: { id: "lanc-1", status: "CONFIRMADO", total: 0 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    await userEvent.click(within(combate1).getByRole("button", { name: /^empate$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ equipe_id: "eq-1", itens: [{ criterio_id: "crit-1", ocorrencias: 0 }] }),
        }),
      ),
    );
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ equipe_id: "eq-2", itens: [{ criterio_id: "crit-1", ocorrencias: 0 }] }),
        }),
      ),
    );
  });

  it("combate ja decidido mostra o resultado sem os botoes, e nao clicavel de novo", async () => {
    mockGet({
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
      ],
    });

    renderPage();

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    expect(within(combate1).queryByRole("button", { name: /venceu/i })).not.toBeInTheDocument();
    expect(within(combate1).queryByRole("button", { name: /^empate$/i })).not.toBeInTheDocument();
    expect(within(combate1).getByText(/equipe x/i)).toHaveClass("text-emerald-700");
    expect(within(combate1).getByText(/equipe y/i)).toHaveClass("text-red-700");

    const combate2 = (await screen.findByText(/combate 2/i)).closest("li")!;
    expect(within(combate2).getByRole("button", { name: /^equipe x$/i })).toBeInTheDocument();
  });

  it("mostra o vencedor final no topo quando a partida ja fechou", async () => {
    mockGet({
      partida: { status: "ENCERRADA", vencedor_id: "eq-1" },
      lancamentos: [1, 2, 3].flatMap((t) => [
        { id: `la${t}`, equipe_id: "eq-1", tentativa: t, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: `lb${t}`, equipe_id: "eq-2", tentativa: t, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
      ]),
    });

    renderPage();

    expect(await screen.findByText(/vencedor.*equipe x/i)).toBeInTheDocument();
  });

  it("mostra 'partida empatada' no topo quando a partida fecha empatada", async () => {
    mockGet({ partida: { status: "EMPATADA", vencedor_id: null } });

    renderPage();

    expect(await screen.findByText(/partida empatada/i)).toBeInTheDocument();
  });

  it("mostra aviso de empate tecnico quando os 3 combates fecham empatados em vitorias, oferecendo o combate extra", async () => {
    mockGet({
      partida: { status: "AGENDADA", vencedor_id: null },
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l3", equipe_id: "eq-1", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l4", equipe_id: "eq-2", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l5", equipe_id: "eq-1", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l6", equipe_id: "eq-2", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
      ],
    });

    renderPage();

    expect(await screen.findByText(/combate extra de desempate/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/precisa de corre[cç][aã]o do coordenador/i),
    ).not.toBeInTheDocument();
  });

  it("mostra aviso de correcao do coordenador quando o combate extra tambem empata", async () => {
    mockGet({
      partida: { status: "AGENDADA", vencedor_id: null },
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l3", equipe_id: "eq-1", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l4", equipe_id: "eq-2", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l5", equipe_id: "eq-1", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l6", equipe_id: "eq-2", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l7", equipe_id: "eq-1", tentativa: 4, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l8", equipe_id: "eq-2", tentativa: 4, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
      ],
    });

    renderPage();

    expect(
      await screen.findByText(/precisa de corre[cç][aã]o do coordenador/i),
    ).toBeInTheDocument();
  });

  it("mostra o combate extra de desempate quando os 3 combates empatam, sem opcao de empate", async () => {
    mockGet({
      partida: { status: "AGENDADA", vencedor_id: null },
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l3", equipe_id: "eq-1", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l4", equipe_id: "eq-2", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l5", equipe_id: "eq-1", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l6", equipe_id: "eq-2", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
      ],
    });

    renderPage();

    const secao = (await screen.findByText(/^combate extra \(desempate\)$/i)).closest("div")!;
    expect(within(secao).getByRole("button", { name: /^equipe x$/i })).toBeInTheDocument();
    expect(within(secao).getByRole("button", { name: /^equipe y$/i })).toBeInTheDocument();
    expect(within(secao).queryByRole("button", { name: /^empate$/i })).not.toBeInTheDocument();
  });

  it("clicar no combate extra de desempate registra e confirma na tentativa seguinte", async () => {
    mockGet({
      partida: { status: "AGENDADA", vencedor_id: null },
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l3", equipe_id: "eq-1", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l4", equipe_id: "eq-2", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l5", equipe_id: "eq-1", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l6", equipe_id: "eq-2", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
      ],
    });
    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/lancamentos") {
        const body = (opts as { body: { equipe_id: string } }).body;
        return { data: { id: `lanc-${body.equipe_id}`, status: "PENDENTE", total: 0 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        return { data: { id: "lanc-1", status: "CONFIRMADO", total: 0 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const secao = (await screen.findByText(/^combate extra \(desempate\)$/i)).closest("div")!;
    await userEvent.click(within(secao).getByRole("button", { name: /^equipe x$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({
            equipe_id: "eq-1",
            tentativa: 4,
            partida_id: "par-1",
            itens: [{ criterio_id: "crit-1", ocorrencias: 1 }],
          }),
        }),
      ),
    );
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({
            equipe_id: "eq-2",
            tentativa: 4,
            partida_id: "par-1",
            itens: [{ criterio_id: "crit-1", ocorrencias: 0 }],
          }),
        }),
      ),
    );
  });

  it("nao mostra aviso de empate tecnico quando a partida ja fechou normalmente", async () => {
    mockGet({
      partida: { status: "ENCERRADA", vencedor_id: "eq-1" },
      lancamentos: [1, 2, 3].flatMap((t) => [
        { id: `la${t}`, equipe_id: "eq-1", tentativa: t, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: `lb${t}`, equipe_id: "eq-2", tentativa: t, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
      ]),
    });

    renderPage();

    await screen.findByText(/vencedor.*equipe x/i);
    expect(screen.queryByText(/precisa de corre[cç][aã]o do coordenador/i)).not.toBeInTheDocument();
  });
});

describe("PartidaScorerPage - volta automatica pro Pontuar", () => {
  it("volta pra tela de pontuar assim que a partida fecha, pra agilizar lançar varias partidas seguidas", async () => {
    let decidida = false;

    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        const partida = decidida
          ? { ...PARTIDA_BASE, status: "ENCERRADA", vencedor_id: "eq-1" }
          : PARTIDA_BASE;
        return { data: [partida], error: undefined } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: {
            id: "mod-1",
            nome: "Sumo de Robos",
            ficha_unica_entre_niveis: true,
            tentativas_por_rodada: 1,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas") {
        return {
          data: {
            itens: [{ id: FICHA_BOOLEANA.id, nivel: null, status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas/{ficha_id}") {
        return { data: FICHA_BOOLEANA, error: undefined } as never;
      }
      if (path === "/api/v1/equipes") {
        return { data: { itens: EQUIPES, total: 2, page: 1, size: 200 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos") {
        return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/lancamentos") {
        const body = (opts as { body: { equipe_id: string } }).body;
        return { data: { id: `lanc-${body.equipe_id}`, status: "PENDENTE", total: 0 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        decidida = true;
        return { data: { id: "lanc-1", status: "CONFIRMADO", total: 0 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    await userEvent.click(within(combate1).getByRole("button", { name: /^equipe x$/i }));

    expect(await screen.findByText("TELA DE PONTUAR")).toBeInTheDocument();
  });

  it("nao volta automaticamente enquanto a partida ainda nao fechou (empate tecnico)", async () => {
    mockGet({
      partida: { status: "AGENDADA", vencedor_id: null },
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l3", equipe_id: "eq-1", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l4", equipe_id: "eq-2", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
      ],
      tentativasPorRodada: 3,
    });

    renderPage();

    await screen.findByText(/combate 3/i);
    expect(screen.queryByText("TELA DE PONTUAR")).not.toBeInTheDocument();
  });
});


describe("PartidaScorerPage - ficha com um criterio escala", () => {
  it("mostra os botoes de resultado por equipe, com os rotulos Arrasto parcial / Arrasto pro fosso, mais Empate", async () => {
    mockGet({ ficha: FICHA_ESCALA, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    expect(within(combate1).getByText(/defina o resultado/i)).toBeInTheDocument();
    expect(within(combate1).getAllByRole("button", { name: /^arrasto parcial$/i })).toHaveLength(2);
    expect(within(combate1).getAllByRole("button", { name: /^arrasto pro fosso$/i })).toHaveLength(2);
    expect(within(combate1).getByRole("button", { name: /^empate$/i })).toBeInTheDocument();
    expect(within(combate1).queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("clicar 'Arrasto pro fosso' da Equipe X registra Equipe X com valor 2 e Equipe Y com valor 0", async () => {
    mockGet({ ficha: FICHA_ESCALA, tentativasPorRodada: 1 });
    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/lancamentos") {
        const body = (opts as { body: { equipe_id: string } }).body;
        return { data: { id: `lanc-${body.equipe_id}`, status: "PENDENTE", total: 0 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        return { data: { id: "lanc-1", status: "CONFIRMADO", total: 0 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    const grupoX = within(combate1).getByText(/^equipe x$/i).closest("div")!;
    await userEvent.click(within(grupoX).getByRole("button", { name: /^arrasto pro fosso$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ equipe_id: "eq-1", itens: [{ criterio_id: "crit-2", valor: 2 }] }),
        }),
      ),
    );
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ equipe_id: "eq-2", itens: [{ criterio_id: "crit-2", valor: 0 }] }),
        }),
      ),
    );
  });

  it("clicar 'Empate' registra os dois lados com valor 0", async () => {
    mockGet({ ficha: FICHA_ESCALA, tentativasPorRodada: 1 });
    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/lancamentos") {
        const body = (opts as { body: { equipe_id: string } }).body;
        return { data: { id: `lanc-${body.equipe_id}`, status: "PENDENTE", total: 0 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        return { data: { id: "lanc-1", status: "CONFIRMADO", total: 0 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    await userEvent.click(within(combate1).getByRole("button", { name: /^empate$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ equipe_id: "eq-1", itens: [{ criterio_id: "crit-2", valor: 0 }] }),
        }),
      ),
    );
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ equipe_id: "eq-2", itens: [{ criterio_id: "crit-2", valor: 0 }] }),
        }),
      ),
    );
  });
});

describe("PartidaScorerPage - ficha com mais de um criterio (fallback)", () => {
  it("mostra link pra ficha completa em vez dos botoes simplificados", async () => {
    mockGet({ ficha: FICHA_MULTI, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    expect(within(combate1).queryByRole("button", { name: /venceu/i })).not.toBeInTheDocument();
    const link = within(combate1).getByRole("link", { name: /lan[çc]ar pela ficha completa/i });
    expect(link.getAttribute("href")).toContain("partidaId=par-1");
  });
});
