import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
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

function TelaDePontuar() {
  const location = useLocation();
  return <div>TELA DE PONTUAR{location.search}</div>;
}

function renderPage(caminho = ROTA) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[caminho]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas/:rodadaId/partidas/:partidaId/pontuar"
            element={<PartidaScorerPage />}
          />
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/pontuar"
            element={<TelaDePontuar />}
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

const FICHA_ESCALA_SUMO = {
  id: "ficha-2b",
  grupos: [
    {
      id: "grupo-1",
      nome: "Geral",
      criterios: [
        {
          id: "crit-2b",
          nome: "Resultado do combate",
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
          nome: "Vantagem",
          categoria: "PONTUACAO",
          tipo: "BOOLEANO",
          pontos: 5,
          valores_permitidos: null,
          max_ocorrencias: null,
        },
        {
          id: "crit-4b",
          nome: "Falta Grave",
          categoria: "PENALIDADE",
          tipo: "BOOLEANO",
          pontos: 3,
          valores_permitidos: null,
          max_ocorrencias: null,
        },
      ],
    },
  ],
};

const FICHA_NAO_SUPORTADA_INLINE = {
  id: "ficha-4",
  grupos: [
    {
      id: "grupo-1",
      nome: "Geral",
      criterios: [
        {
          id: "crit-5",
          nome: "Ataque",
          categoria: "PONTUACAO",
          tipo: "CONTADOR",
          pontos: 10,
          valores_permitidos: null,
          max_ocorrencias: null,
        },
        {
          id: "crit-6",
          nome: "Nota Tecnica",
          categoria: "PONTUACAO",
          tipo: "ESCALA",
          pontos: null,
          valores_permitidos: [0, 2, 5],
          max_ocorrencias: null,
        },
      ],
    },
  ],
};

interface MockConfig {
  partida?: Record<string, unknown>;
  ficha?:
    | typeof FICHA_BOOLEANA
    | typeof FICHA_ESCALA
    | typeof FICHA_ESCALA_SUMO
    | typeof FICHA_MULTI
    | typeof FICHA_NAO_SUPORTADA_INLINE;
  tentativasPorRodada?: number;
  lancamentos?: unknown[];
  decisaoPartida?: string;
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
          decisao_partida: cfg.decisaoPartida ?? "COMBATES_VENCIDOS",
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

  it("com decisao_partida SOMA_PONTOS, libera o combate extra pela soma empatada mesmo com contagem de combates diferente", async () => {
    mockGet({
      partida: { status: "AGENDADA", vencedor_id: null },
      decisaoPartida: "SOMA_PONTOS",
      // equipe X vence 2 combates (1 e 2), equipe Y vence so 1 (3) - por
      // CONTAGEM nao empataria (2 a 1), mas a SOMA empata (2 a 2), que e o
      // que decide de verdade com SOMA_PONTOS.
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l3", equipe_id: "eq-1", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 1 },
        { id: "l4", equipe_id: "eq-2", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l5", equipe_id: "eq-1", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l6", equipe_id: "eq-2", tentativa: 3, partida_id: "par-1", status: "CONFIRMADO", total: 2 },
      ],
    });

    renderPage();

    expect(await screen.findByText(/combate extra de desempate/i)).toBeInTheDocument();
  });

  it("com decisao_partida SOMA_PONTOS, nao libera o combate extra quando a soma ja decide (mesmo com 1 combate vencido cada)", async () => {
    mockGet({
      partida: { status: "AGENDADA", vencedor_id: null },
      decisaoPartida: "SOMA_PONTOS",
      tentativasPorRodada: 2,
      // equipe X vence o combate 1 por 20x0, equipe Y vence o combate 2 por
      // 0x10 - 1 combate vencido cada, mas a soma (20 contra 10) ja decide,
      // sem precisar de combate extra.
      lancamentos: [
        { id: "l1", equipe_id: "eq-1", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 20 },
        { id: "l2", equipe_id: "eq-2", tentativa: 1, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l3", equipe_id: "eq-1", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 0 },
        { id: "l4", equipe_id: "eq-2", tentativa: 2, partida_id: "par-1", status: "CONFIRMADO", total: 10 },
      ],
    });

    renderPage();

    await screen.findByText(/^combate 1$/i);
    expect(screen.queryByText(/combate extra de desempate/i)).not.toBeInTheDocument();
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

describe("PartidaScorerPage - retry apos falha parcial", () => {
  it("depois da confirmacao do 2o lado falhar, um novo clique nao recria o lancamento ja confirmado nem o que ja ficou pendente", async () => {
    let lancamentosDinamico: Record<string, unknown>[] = [];
    let falharConfirmarEq2 = true;

    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return { data: [PARTIDA_BASE], error: undefined } as never;
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
        return {
          data: { itens: lancamentosDinamico, total: lancamentosDinamico.length, page: 1, size: 200 },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/lancamentos") {
        const body = (opts as { body: { equipe_id: string } }).body;
        const novo = {
          id: `lanc-${body.equipe_id}`,
          equipe_id: body.equipe_id,
          tentativa: 1,
          partida_id: "par-1",
          status: "PENDENTE",
          total: 0,
        };
        lancamentosDinamico = [...lancamentosDinamico, novo];
        return { data: novo, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        const { lancamento_id } = (
          opts as { params: { path: { lancamento_id: string } } }
        ).params.path;
        if (lancamento_id === "lanc-eq-2" && falharConfirmarEq2) {
          return {
            data: undefined,
            error: { erro: { codigo: "ERRO_TESTE", mensagem: "Falha de rede" } },
          } as never;
        }
        lancamentosDinamico = lancamentosDinamico.map((l) =>
          l.id === lancamento_id ? { ...l, status: "CONFIRMADO" } : l,
        );
        return { data: { id: lancamento_id, status: "CONFIRMADO", total: 0 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    await userEvent.click(within(combate1).getByRole("button", { name: /^equipe x$/i }));

    await waitFor(() => expect(screen.getByText(/falha de rede/i)).toBeInTheDocument());

    vi.mocked(api.POST).mockClear();
    falharConfirmarEq2 = false;

    await userEvent.click(within(combate1).getByRole("button", { name: /^equipe x$/i }));

    await waitFor(() => expect(screen.queryByText(/falha de rede/i)).not.toBeInTheDocument());

    const todasAsChamadas = vi.mocked(api.POST).mock.calls as unknown as [string, unknown][];
    const chamadasCriar = todasAsChamadas.filter(([caminho]) => caminho === "/api/v1/lancamentos");
    expect(chamadasCriar).toHaveLength(0);
    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/lancamentos/{lancamento_id}/confirmar",
      expect.objectContaining({ params: { path: { lancamento_id: "lanc-eq-2" } } }),
    );
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

  it("preserva o filtro de nivel (?nivel=) da url ao voltar pra tela de pontuar", async () => {
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

    renderPage(`${ROTA}?nivel=2`);

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    await userEvent.click(within(combate1).getByRole("button", { name: /^equipe x$/i }));

    expect(await screen.findByText("TELA DE PONTUAR?nivel=2")).toBeInTheDocument();
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

  it("mostra os botoes de resultado do sumo, com os rotulos Waza-ari / Ippon, mais Empate", async () => {
    mockGet({ ficha: FICHA_ESCALA_SUMO, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    expect(within(combate1).getByText(/defina o resultado/i)).toBeInTheDocument();
    expect(within(combate1).getAllByRole("button", { name: /^waza-ari$/i })).toHaveLength(2);
    expect(within(combate1).getAllByRole("button", { name: /^ippon$/i })).toHaveLength(2);
    expect(within(combate1).getByRole("button", { name: /^empate$/i })).toBeInTheDocument();
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

describe("PartidaScorerPage - ficha com varios criterios BOOLEANO/CONTADOR (scorer inline)", () => {
  it("mostra os criterios organizados por equipe, com botao pra BOOLEANO e contador +/- pra CONTADOR", async () => {
    mockGet({ ficha: FICHA_MULTI, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    expect(
      within(combate1).queryByRole("link", { name: /lan[çc]ar pela ficha completa/i }),
    ).not.toBeInTheDocument();

    const blocoA = within(combate1).getByText(/^equipe x$/i).closest("div")!;
    const blocoB = within(combate1).getByText(/^equipe y$/i).closest("div")!;

    expect(within(blocoA).getByRole("button", { name: "Vantagem" })).toBeInTheDocument();
    expect(within(blocoB).getByRole("button", { name: "Vantagem" })).toBeInTheDocument();
    expect(within(blocoA).getByText("Ataque")).toBeInTheDocument();
    expect(within(blocoA).getByRole("button", { name: /aumentar ataque/i })).toBeInTheDocument();
    expect(within(blocoA).getByRole("button", { name: /diminuir ataque/i })).toBeInTheDocument();

    expect(
      within(combate1).getByRole("button", { name: /^registrar$/i }),
    ).toBeInTheDocument();
  });

  it("colore de verde o criterio que faz a equipe ganhar e de vermelho o que faz perder", async () => {
    mockGet({ ficha: FICHA_MULTI, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    const blocoA = within(combate1).getByText(/^equipe x$/i).closest("div")!;

    const botaoVantagem = within(blocoA).getByRole("button", { name: "Vantagem" });
    const botaoFalta = within(blocoA).getByRole("button", { name: "Falta Grave" });

    expect(botaoVantagem.className).toMatch(/emerald/);
    expect(botaoVantagem.className).not.toMatch(/red/);
    expect(botaoFalta.className).toMatch(/red/);
    expect(botaoFalta.className).not.toMatch(/emerald/);

    await userEvent.click(botaoVantagem);
    await userEvent.click(botaoFalta);

    expect(botaoVantagem.className).toMatch(/emerald/);
    expect(botaoFalta.className).toMatch(/red/);
  });

  it("registra os itens marcados por equipe ao clicar em Registrar", async () => {
    mockGet({ ficha: FICHA_MULTI, tentativasPorRodada: 1 });
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
    const blocoA = within(combate1).getByText(/^equipe x$/i).closest("div")!;
    const blocoB = within(combate1).getByText(/^equipe y$/i).closest("div")!;

    await userEvent.click(within(blocoA).getByRole("button", { name: /aumentar ataque/i }));
    await userEvent.click(within(blocoA).getByRole("button", { name: /aumentar ataque/i }));
    await userEvent.click(within(blocoB).getByRole("button", { name: "Vantagem" }));

    await userEvent.click(within(combate1).getByRole("button", { name: /^registrar$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({
            equipe_id: "eq-1",
            itens: [{ criterio_id: "crit-3", ocorrencias: 2 }],
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
            itens: [{ criterio_id: "crit-4", ocorrencias: 1 }],
          }),
        }),
      ),
    );
  });

  it("marcar um criterio booleano pra uma equipe desmarca o mesmo criterio da outra", async () => {
    mockGet({ ficha: FICHA_MULTI, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    const blocoA = within(combate1).getByText(/^equipe x$/i).closest("div")!;
    const blocoB = within(combate1).getByText(/^equipe y$/i).closest("div")!;

    const vantagemA = within(blocoA).getByRole("button", { name: "Vantagem" });
    const vantagemB = within(blocoB).getByRole("button", { name: "Vantagem" });

    await userEvent.click(vantagemA);
    expect(vantagemA).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(vantagemB);
    expect(vantagemB).toHaveAttribute("aria-pressed", "true");
    expect(vantagemA).toHaveAttribute("aria-pressed", "false");
  });

  it("o contador (Evitar a colisao) fica independente pras duas equipes ao mesmo tempo", async () => {
    mockGet({ ficha: FICHA_MULTI, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/^combate 1$/i)).closest("li")!;
    const blocoA = within(combate1).getByText(/^equipe x$/i).closest("div")!;
    const blocoB = within(combate1).getByText(/^equipe y$/i).closest("div")!;

    await userEvent.click(within(blocoA).getByRole("button", { name: /aumentar ataque/i }));
    await userEvent.click(within(blocoB).getByRole("button", { name: /aumentar ataque/i }));

    expect(within(blocoA).getByText("1")).toBeInTheDocument();
    expect(within(blocoB).getByText("1")).toBeInTheDocument();
  });
});

describe("PartidaScorerPage - ficha com criterio nao suportado pelo scorer inline (fallback)", () => {
  it("mostra link pra ficha completa quando algum criterio nao e BOOLEANO/CONTADOR", async () => {
    mockGet({ ficha: FICHA_NAO_SUPORTADA_INLINE, tentativasPorRodada: 1 });

    renderPage();

    const combate1 = (await screen.findByText(/combate 1/i)).closest("li")!;
    expect(within(combate1).queryByRole("button", { name: /venceu/i })).not.toBeInTheDocument();
    const link = within(combate1).getByRole("link", { name: /lan[çc]ar pela ficha completa/i });
    expect(link.getAttribute("href")).toContain("partidaId=par-1");
  });
});
