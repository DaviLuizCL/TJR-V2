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
