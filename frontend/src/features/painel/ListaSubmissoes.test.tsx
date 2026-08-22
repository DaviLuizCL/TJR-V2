import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ListaSubmissoes } from "./ListaSubmissoes";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderLista() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ListaSubmissoes modalidadeId="mod-1" />
    </QueryClientProvider>,
  );
}

function mockGet(itens: unknown[]) {
  vi.mocked(api.GET).mockResolvedValue({
    data: { itens, total: itens.length, page: 1, size: 100 },
    error: undefined,
  } as never);
}

function baseLancamento(overrides: Record<string, unknown>) {
  return {
    id: "lanc-1",
    modalidade_nome: "Exploracao Autonoma",
    nivel: 1,
    equipe_nome: "Equipe Foguete",
    rodada_numero: 1,
    tentativa: 1,
    responsavel_nome: "Joana Arbitra",
    horario_submissao: "2026-03-10T12:00:00Z",
    status: "CONFIRMADO",
    total: 45,
    itens: [],
    partida_id: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ListaSubmissoes - identificacao do lancamento", () => {
  it("mostra o id do lancamento logo apos a tentativa, para referenciar em feedback", async () => {
    mockGet([baseLancamento({ id: "lanc-abc-123", itens: [] })]);

    renderLista();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(card).getByText(/tentativa 1.*lanc-abc-123/i)).toBeInTheDocument();
  });
});

describe("ListaSubmissoes - modificadores", () => {
  it("mostra modificador PERCENTUAL de penalidade aplicado, com o sinal negativo, fora de Não pontuados", async () => {
    mockGet([
      baseLancamento({
        itens: [
          {
            criterio_snapshot: {
              nome: "Excedeu tempo limite",
              categoria: "PENALIDADE",
              tipo: "MODIFICADOR",
              modificador_tipo: "PERCENTUAL",
              modificador_valor: 10,
              aplicado: true,
            },
            pontos: 0,
          },
        ],
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    const secaoModificadores = within(card).getByText(/modificadores/i).closest("div")!;
    expect(within(secaoModificadores).getByText(/excedeu tempo limite/i)).toBeInTheDocument();
    expect(within(secaoModificadores).getByText("-10%")).toBeInTheDocument();

    const secaoZerados = within(card).getByText(/^não pontuados$/i).closest("div")!;
    expect(within(secaoZerados).queryByText(/excedeu tempo limite/i)).not.toBeInTheDocument();
  });

  it("mostra modificador PERCENTUAL de pontuacao aplicado, com o sinal positivo", async () => {
    mockGet([
      baseLancamento({
        itens: [
          {
            criterio_snapshot: {
              nome: "Bonus de precisao",
              categoria: "PONTUACAO",
              tipo: "MODIFICADOR",
              modificador_tipo: "PERCENTUAL",
              modificador_valor: 15,
              aplicado: true,
            },
            pontos: 0,
          },
        ],
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(card).getByText(/bonus de precisao/i)).toBeInTheDocument();
    expect(within(card).getByText("+15%")).toBeInTheDocument();
  });

  it("mostra modificador ZERA_TOTAL aplicado como 'Zera o total'", async () => {
    mockGet([
      baseLancamento({
        itens: [
          {
            criterio_snapshot: {
              nome: "Parou completamente",
              categoria: "PENALIDADE",
              tipo: "MODIFICADOR",
              modificador_tipo: "ZERA_TOTAL",
              modificador_valor: null,
              aplicado: true,
            },
            pontos: 0,
          },
        ],
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(card).getByText(/zera o total/i)).toBeInTheDocument();
  });

  it("mostra modificador nao aplicado como 'Nao aplicado'", async () => {
    mockGet([
      baseLancamento({
        itens: [
          {
            criterio_snapshot: {
              nome: "Excedeu tempo limite",
              categoria: "PENALIDADE",
              tipo: "MODIFICADOR",
              modificador_tipo: "PERCENTUAL",
              modificador_valor: 10,
              aplicado: false,
            },
            pontos: 0,
          },
        ],
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(card).getByText(/n[ãa]o aplicado/i)).toBeInTheDocument();
  });

  it("nao mostra a secao de modificadores quando nao ha nenhum item desse tipo", async () => {
    mockGet([
      baseLancamento({
        itens: [
          {
            criterio_snapshot: { nome: "Lombada", categoria: "PONTUACAO", tipo: "CONTADOR" },
            pontos: 30,
          },
        ],
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(card).queryByText(/modificadores/i)).not.toBeInTheDocument();
  });

  it("criterio comum zerado continua aparecendo em Nao pontuados", async () => {
    mockGet([
      baseLancamento({
        itens: [
          {
            criterio_snapshot: { nome: "Completou o percurso", categoria: "PONTUACAO", tipo: "BOOLEANO" },
            pontos: 0,
          },
        ],
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Joana Arbitra")).closest("li")!;
    const secaoZerados = within(card).getByText(/^não pontuados$/i).closest("div")!;
    expect(within(secaoZerados).getByText(/completou o percurso/i)).toBeInTheDocument();
  });
});

describe("ListaSubmissoes - modalidades de combate", () => {
  it("agrupa os dois lados da mesma partida+tentativa num card so, com o combate e o resultado", async () => {
    mockGet([
      baseLancamento({
        id: "lanc-a",
        modalidade_nome: "Sumô",
        equipe_nome: "Equipe A",
        partida_id: "partida-1",
        tentativa: 1,
        total: 10,
      }),
      baseLancamento({
        id: "lanc-b",
        modalidade_nome: "Sumô",
        equipe_nome: "Equipe B",
        partida_id: "partida-1",
        tentativa: 1,
        total: 4,
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Equipe A")).closest("li")!;
    expect(within(card).getByText("Equipe B")).toBeInTheDocument();
    expect(within(card).getByText(/rodada 1/i)).toBeInTheDocument();
    expect(within(card).getByText(/tentativa 1/i)).toBeInTheDocument();
    // Nao mostra a grade detalhada de criterio por criterio de CardSubmissao.
    expect(within(card).queryByText(/^pontuados$/i)).not.toBeInTheDocument();
    // So um card na lista, nao dois separados.
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });

  it("destaca o lado vencedor pelo total de cada lado", async () => {
    mockGet([
      baseLancamento({
        id: "lanc-a",
        equipe_nome: "Equipe A",
        partida_id: "partida-1",
        tentativa: 1,
        total: 10,
      }),
      baseLancamento({
        id: "lanc-b",
        equipe_nome: "Equipe B",
        partida_id: "partida-1",
        tentativa: 1,
        total: 4,
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Equipe A")).closest("li")!;
    const ladoA = within(card).getByText("Equipe A").closest("div")!;
    const ladoB = within(card).getByText("Equipe B").closest("div")!;
    expect(within(ladoA).getByText(/vencedor/i)).toBeInTheDocument();
    expect(within(ladoB).queryByText(/vencedor/i)).not.toBeInTheDocument();
  });

  it("mostra Empate quando os dois lados da partida tem o mesmo total", async () => {
    mockGet([
      baseLancamento({
        id: "lanc-a",
        equipe_nome: "Equipe A",
        partida_id: "partida-1",
        tentativa: 1,
        total: 5,
      }),
      baseLancamento({
        id: "lanc-b",
        equipe_nome: "Equipe B",
        partida_id: "partida-1",
        tentativa: 1,
        total: 5,
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Equipe A")).closest("li")!;
    expect(within(card).getAllByText(/empate/i).length).toBeGreaterThan(0);
    expect(within(card).queryByText(/vencedor/i)).not.toBeInTheDocument();
  });

  it("mostra 'aguardando a equipe adversaria' quando so um lado da partida foi lancado", async () => {
    mockGet([
      baseLancamento({
        id: "lanc-a",
        equipe_nome: "Equipe A",
        partida_id: "partida-1",
        tentativa: 1,
        total: 10,
      }),
    ]);

    renderLista();

    const card = (await screen.findByText("Equipe A")).closest("li")!;
    expect(within(card).getByText(/aguardando/i)).toBeInTheDocument();
  });

  it("lancamentos de partidas diferentes viram cards separados", async () => {
    mockGet([
      baseLancamento({
        id: "lanc-a",
        equipe_nome: "Equipe A",
        partida_id: "partida-1",
        tentativa: 1,
        total: 10,
      }),
      baseLancamento({
        id: "lanc-c",
        equipe_nome: "Equipe C",
        partida_id: "partida-2",
        tentativa: 1,
        total: 7,
      }),
    ]);

    renderLista();

    await screen.findByText("Equipe A");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
});
