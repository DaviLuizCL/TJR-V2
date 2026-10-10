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

  it("ordena as equipes da mesma rodada pela sequencia de competicao sorteada", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Alfa", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Beta", nivel: 1, ativo: true },
        { id: "eq-3", nome: "Gama", nivel: 1, ativo: true },
      ],
      inscricoes: [
        { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1", ordem_apresentacao: 3 },
        { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1", ordem_apresentacao: 1 },
        { id: "ins-3", equipe_id: "eq-3", modalidade_id: "mod-1", ordem_apresentacao: 2 },
      ],
    });

    renderPage();

    await screen.findByText("Alfa");
    const nomes = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(nomes).toEqual(["Beta", "Gama", "Alfa"]);
  });

  it("mostra a posicao da equipe na sequencia de competicao no card", async () => {
    mockGet({
      inscricoes: [
        { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1", ordem_apresentacao: 2 },
        { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1", ordem_apresentacao: 1 },
      ],
    });

    renderPage();

    const cardX = (await screen.findByText("Equipe X")).closest("a")!;
    expect(within(cardX).getByText(/2º na sequ[eê]ncia/i)).toBeInTheDocument();
  });

  it("equipe sem ordem sorteada vai pro fim da rodada, em ordem alfabetica", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Alfa", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Beta", nivel: 1, ativo: true },
      ],
      inscricoes: [
        { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1", ordem_apresentacao: null },
        { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1", ordem_apresentacao: 1 },
      ],
    });

    renderPage();

    await screen.findByText("Alfa");
    const nomes = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(nomes).toEqual(["Beta", "Alfa"]);
  });

  it("nao busca arena nem agendamento (arena e decidida na hora)", async () => {
    mockGet();

    renderPage();

    await screen.findByText("Equipe X");
    const caminhos = vi.mocked(api.GET).mock.calls.map((c) => c[0]);
    expect(caminhos).not.toContain("/api/v1/arenas");
    expect(caminhos).not.toContain("/api/v1/agendamentos");
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
    // Arena/horario sairam do sistema -- "sem rodada" se resolve direto na
    // tela de Rodadas da modalidade, que tem o botao "Gerar rodadas".
    expect(screen.getByRole("link", { name: /gerar rodadas/i })).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas",
    );
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

  it("mostra o filtro de rodada quando a modalidade tem mais de uma rodada", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByLabelText(/filtrar por rodada/i)).toBeInTheDocument();
  });

  it("nao mostra o filtro de rodada quando so existe uma rodada", async () => {
    mockGet({ rodadas: [{ id: "rod-1", modalidade_id: "mod-1", numero: 1 }] });

    renderPage();

    await screen.findByText("Equipe X");
    expect(screen.queryByLabelText(/filtrar por rodada/i)).not.toBeInTheDocument();
  });

  it("filtra os cards pendentes pela rodada selecionada", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();
    await screen.findByText("Equipe X");

    await userEvent.selectOptions(screen.getByLabelText(/filtrar por rodada/i), "1");
    expect(screen.getByText("Equipe X")).toBeInTheDocument();
    expect(screen.queryByText("Equipe Y")).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/filtrar por rodada/i), "2");
    expect(screen.queryByText("Equipe X")).not.toBeInTheDocument();
    expect(screen.getByText("Equipe Y")).toBeInTheDocument();
  });

  it("filtro de nivel e de rodada funcionam juntos, sem um resetar o outro", async () => {
    mockGet({
      equipes: [
        { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
        { id: "eq-2", nome: "Equipe Y", nivel: 2, ativo: true },
      ],
    });

    renderPage();
    await screen.findByText("Equipe X");

    await userEvent.selectOptions(screen.getByLabelText(/filtrar por nivel/i), "1");
    await userEvent.selectOptions(screen.getByLabelText(/filtrar por rodada/i), "1");

    expect((screen.getByLabelText(/filtrar por nivel/i) as HTMLSelectElement).value).toBe("1");
    expect((screen.getByLabelText(/filtrar por rodada/i) as HTMLSelectElement).value).toBe("1");
    expect(screen.getByText("Equipe X")).toBeInTheDocument();
    expect(screen.queryByText("Equipe Y")).not.toBeInTheDocument();
  });

  it("abrir a pagina com ?rodada= na url ja vem com essa rodada selecionada no filtro", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage("/eventos/evt-1/modalidades/mod-1/pontuar?rodada=2");

    const select = (await screen.findByLabelText(/filtrar por rodada/i)) as HTMLSelectElement;
    expect(select.value).toBe("2");
    expect(await screen.findByText("Equipe Y")).toBeInTheDocument();
    expect(screen.queryByText("Equipe X")).not.toBeInTheDocument();
  });

  it("mostra mensagem quando o filtro de rodada nao bate com nenhuma equipe pendente", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [
          { id: "l1", equipe_id: "eq-1", tentativa: 1, status: "CONFIRMADO" },
          { id: "l2", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" },
        ],
      },
    });

    renderPage();
    await userEvent.selectOptions(await screen.findByLabelText(/filtrar por rodada/i), "1");

    expect(
      await screen.findByText(/nenhuma equipe pendente na rodada selecionada/i),
    ).toBeInTheDocument();
  });

  it("escolher uma rodada no filtro atualiza a url e o card da equipe carrega a rodada junto", async () => {
    mockGet({
      lancamentosPorRodada: {
        "rod-1": [{ id: "l1", equipe_id: "eq-2", tentativa: 1, status: "CONFIRMADO" }],
      },
    });

    renderPage();
    await userEvent.selectOptions(await screen.findByLabelText(/filtrar por rodada/i), "1");

    const card = (await screen.findByText("Equipe X")).closest("a")!;
    expect(card).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1&rodada=1",
    );
  });
});
