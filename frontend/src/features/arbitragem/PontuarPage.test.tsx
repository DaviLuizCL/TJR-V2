import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PontuarPage } from "./PontuarPage";

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
            element={<PontuarPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

interface MockConfig {
  tentativasPorRodada?: number;
  lancamentosPorRodada?: Record<string, unknown[]>;
  arenas?: unknown[];
  agendamentos?: unknown[];
  equipes?: unknown[];
  inscricoes?: unknown[];
  rodadas?: unknown[];
}

function mockGet(cfg: MockConfig = {}) {
  const equipes = cfg.equipes ?? [
    { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
    { id: "eq-2", nome: "Equipe Y", nivel: 1, ativo: true },
  ];
  const inscricoes = cfg.inscricoes ?? [
    { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
    { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
  ];

  vi.mocked(api.GET).mockImplementation(async (path: string, opts?: unknown) => {
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return {
        data: {
          id: "mod-1",
          nome: "Resgate no Plano",
          tipo_disputa: "INDIVIDUAL",
          tentativas_por_rodada: cfg.tentativasPorRodada ?? 1,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/rodadas") {
      const rodadas = cfg.rodadas ?? [
        { id: "rod-1", modalidade_id: "mod-1", numero: 1 },
        { id: "rod-2", modalidade_id: "mod-1", numero: 2 },
      ];
      return {
        data: { itens: rodadas, total: rodadas.length, page: 1, size: 200 },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/inscricoes") {
      return { data: { itens: inscricoes, total: inscricoes.length, page: 1, size: 100 }, error: undefined } as never;
    }
    if (path === "/api/v1/equipes") {
      return { data: { itens: equipes, total: equipes.length, page: 1, size: 200 }, error: undefined } as never;
    }
    if (path === "/api/v1/lancamentos") {
      const params = opts as { params: { query: { rodada_id: string } } };
      const rodadaId = params.params.query.rodada_id;
      return {
        data: {
          itens: cfg.lancamentosPorRodada?.[rodadaId] ?? [],
          total: 0,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/arenas") {
      const arenas = cfg.arenas ?? [
        { id: "are-padrao", modalidade_id: "mod-1", nome: "Arena Padrão", niveis_aplicaveis: null, ativo: true },
      ];
      return {
        data: { itens: arenas, total: arenas.length, page: 1, size: 200 },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/agendamentos") {
      // Por padrao, toda equipe inscrita ja tem arena atribuida em rod-1 e rod-2
      // (cobre os cenarios de teste que nao envolvem a regra de arena em si).
      // Testes que exercitam especificamente a ausencia de agendamento passam
      // `agendamentos` explicitamente (inclusive `[]`).
      const agendamentosPadrao = (equipes as { id: string }[]).flatMap((equipe) => [
        { id: `ag-${equipe.id}-rod-1`, rodada_id: "rod-1", equipe_id: equipe.id, arena_id: "are-padrao", ordem_na_arena: 0, horario_inicio: "2026-08-10T08:00:00Z" },
        { id: `ag-${equipe.id}-rod-2`, rodada_id: "rod-2", equipe_id: equipe.id, arena_id: "are-padrao", ordem_na_arena: 0, horario_inicio: "2026-08-10T09:00:00Z" },
      ]);
      const agendamentos = cfg.agendamentos ?? agendamentosPadrao;
      return {
        data: { itens: agendamentos, total: agendamentos.length, page: 1, size: 200 },
        error: undefined,
      } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PontuarPage", () => {
  it("mostra um card por equipe com a proxima rodada pendente dela", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("a")!;
    expect(within(cardX).getByText(/rodada 1/i)).toBeInTheDocument();

    const cardY = screen.getByText("Equipe Y").closest("a")!;
    expect(within(cardY).getByText(/rodada 2/i)).toBeInTheDocument();
  });

  it("mostra aviso de lancamento pendente de confirmacao quando a equipe tem um em aberto", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-1", tentativa: 1, status: "PENDENTE" }],
      },
    });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("a")!;
    expect(within(cardX).getByText(/pendente de confirma[çc][ãa]o/i)).toBeInTheDocument();

    const cardY = screen.getByText("Equipe Y").closest("a")!;
    expect(within(cardY).queryByText(/pendente de confirma[çc][ãa]o/i)).not.toBeInTheDocument();
  });

  it("nao mostra aviso de pendente quando o lancamento ja esta confirmado", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-1", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("a")!;
    expect(within(cardX).queryByText(/pendente de confirma[çc][ãa]o/i)).not.toBeInTheDocument();
  });

  it("ordena as equipes mais atrasadas primeiro", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();

    await screen.findByText("Equipe X");
    const nomes = screen.getAllByRole("heading", { level: 2 }).map((el) => el.textContent);
    expect(nomes).toEqual(["Equipe X", "Equipe Y"]);
  });

  it("mostra a tentativa quando a modalidade tem mais de uma por rodada", async () => {
    mockGet({
      tentativasPorRodada: 2,
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-1", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("a")!;
    expect(within(cardX).getByText(/rodada 1/i)).toBeInTheDocument();
    expect(within(cardX).getByText(/tentativa 2/i)).toBeInTheDocument();
  });

  it("card linka direto pro formulario de lancamento com equipe e tentativa na url", async () => {
    mockGet({ tentativasPorRodada: 2 });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("a")!;
    expect(cardX).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1",
    );
  });

  it("equipe sem arena atribuida na rodada pendente nao fica clicavel e mostra aviso", async () => {
    mockGet({ agendamentos: [] });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("li")!;
    expect(within(cardX).queryByRole("link", { name: /rodada/i })).not.toBeInTheDocument();
    expect(within(cardX).getByText(/sem arena atribu[ií]da/i)).toBeInTheDocument();
  });

  it("card sem arena atribuida linka pra tela de horarios da modalidade", async () => {
    mockGet({ agendamentos: [] });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("li")!;
    const linkHorarios = within(cardX).getByRole("link", { name: /gerar hor[aá]rio/i });
    expect(linkHorarios).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/horarios",
    );
  });

  it("so a equipe sem arena atribuida fica bloqueada, as outras continuam normais", async () => {
    mockGet({
      agendamentos: [
        { id: "ag-1", rodada_id: "rod-1", equipe_id: "eq-2", arena_id: "are-padrao", ordem_na_arena: 0, horario_inicio: "2026-08-10T08:00:00Z" },
      ],
    });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("li")!;
    expect(within(cardX).getByText(/sem arena atribu[ií]da/i)).toBeInTheDocument();

    const cardY = screen.getByText("Equipe Y").closest("li")!;
    expect(within(cardY).queryByText(/sem arena atribu[ií]da/i)).not.toBeInTheDocument();
    expect(within(cardY).getByRole("link", { name: /rodada/i })).toBeInTheDocument();
  });

  it("equipe que ja completou todas as rodadas/tentativas nao aparece nos cards pendentes", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
        "rod-2": [{ id: "l2", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();

    await screen.findByText("Equipe X");
    expect(screen.queryByText("Equipe Y")).not.toBeInTheDocument();
    expect(screen.getByText(/1 equipe.*completa/i)).toBeInTheDocument();
  });

  it("mostra o filtro de nivel quando as equipes inscritas tem niveis diferentes", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 3, ativo: true },
      ],
    });

    renderPage();

    expect(await screen.findByLabelText(/filtrar por nivel/i)).toBeInTheDocument();
  });

  it("nao mostra o filtro de nivel quando todas as equipes inscritas sao do mesmo nivel", async () => {
    mockGet();

    renderPage();

    await screen.findByText("Equipe X");
    expect(screen.queryByLabelText(/filtrar por nivel/i)).not.toBeInTheDocument();
  });

  it("filtra os cards pendentes pelo nivel selecionado", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 3, ativo: true },
      ],
    });

    renderPage();

    await screen.findByText("Equipe X");
    await userEvent.selectOptions(screen.getByLabelText(/filtrar por nivel/i), "3");

    expect(screen.queryByText("Equipe X")).not.toBeInTheDocument();
    expect(screen.getByText("Equipe Y")).toBeInTheDocument();
  });

  it("o contador de equipes completas tambem respeita o filtro de nivel", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 3, ativo: true },
      ],
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
        "rod-2": [{ id: "l2", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();

    await screen.findByText("Equipe X");
    expect(screen.getByText(/1 equipe.*completa/i)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/filtrar por nivel/i), "1");

    expect(screen.queryByText(/equipe.*completa/i)).not.toBeInTheDocument();
  });

  it("mostra arena e horario quando ja existe agendamento pra rodada da equipe", async () => {
    mockGet({
      arenas: [{ id: "are-1", modalidade_id: "mod-1", nome: "Arena A", niveis_aplicaveis: null, ativo: true }],
      agendamentos: [
        {
          id: "ag-1",
          rodada_id: "rod-1",
          equipe_id: "eq-1",
          arena_id: "are-1",
          ordem_na_arena: 0,
          horario_inicio: "2026-08-10T08:00:00Z",
        },
      ],
    });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("a")!;
    expect(within(cardX).getByText(/arena a/i)).toBeInTheDocument();
  });

  it("mostra mensagem quando nao ha nenhuma equipe pendente", async () => {
    mockGet({ equipes: [], inscricoes: [] });

    renderPage();

    expect(await screen.findByText(/nenhuma equipe pendente/i)).toBeInTheDocument();
  });

  it("BUG-03: sem rodada nenhuma criada, mostra aviso especifico em vez de 'todas completaram'", async () => {
    mockGet({ rodadas: [] });

    renderPage();

    expect(await screen.findByText(/nenhuma rodada foi criada/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/todas ja completaram todas as rodadas/i),
    ).not.toBeInTheDocument();
    // Nao pode aparecer nenhuma equipe pendente nem no rodape de completas -
    // sem rodada, nao existe "completou" nem "pendente" possivel ainda.
    expect(screen.queryByText(/equipe.*completa/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Equipe X")).not.toBeInTheDocument();
  });

  it("BUG-03: sem rodada nenhuma criada mas tambem sem equipe inscrita, mantem a mensagem de sem equipe (nao a de sem rodada)", async () => {
    mockGet({ rodadas: [], equipes: [], inscricoes: [] });

    renderPage();

    expect(await screen.findByText(/nenhuma equipe pendente/i)).toBeInTheDocument();
    expect(screen.queryByText(/nenhuma rodada foi criada/i)).not.toBeInTheDocument();
  });

  it("abrir a pagina com ?nivel= na url ja vem com esse nivel selecionado no filtro", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 2, ativo: true },
      ],
      inscricoes: [
        { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
        { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
      ],
    });

    renderPage("/eventos/evt-1/modalidades/mod-1/pontuar?nivel=2");

    const select = (await screen.findByLabelText(/filtrar por nivel/i)) as HTMLSelectElement;
    expect(select.value).toBe("2");
    expect(await screen.findByText("Equipe Y")).toBeInTheDocument();
    expect(screen.queryByText("Equipe X")).not.toBeInTheDocument();
  });

  it("escolher um nivel no filtro atualiza a url e o card da equipe carrega o nivel junto", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 2, ativo: true },
      ],
      inscricoes: [
        { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
        { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
      ],
    });

    renderPage();
    await userEvent.selectOptions(await screen.findByLabelText(/filtrar por nivel/i), "1");

    const card = (await screen.findByText("Equipe X")).closest("a")!;
    expect(card).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1&nivel=1",
    );
  });
});
