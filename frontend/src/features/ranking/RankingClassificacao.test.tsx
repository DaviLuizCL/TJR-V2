import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RankingClassificacao } from "./RankingClassificacao";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
}));

function renderComponent() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RankingClassificacao
        modalidades={[{ id: "m1", nome: "Sumô" }]}
        mensagemVazia="Nenhum ranking liberado ainda."
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RankingClassificacao", () => {
  it("modalidade com niveis em formatos diferentes mostra as colunas certas por nivel, nao a mesma pra todos", async () => {
    // Desde o chaveamento por nivel (gerar_chaveamento_confronto), formato_chaveamento
    // da MODALIDADE fica null pra modalidade auto-decidida -- o formato de verdade
    // agora vem por ITEM (item.formato_chaveamento), porque niveis diferentes da
    // mesma modalidade podem estar em mata-mata e todos-contra-todos ao mesmo tempo.
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        modalidade_id: "m1",
        modalidade_nome: "Sumô",
        tipo_disputa: "CONFRONTO",
        formato_chaveamento: null,
        ranking_liberado: true,
        itens: [
          {
            equipe_id: "e1",
            equipe_nome: "Equipe Nivel 2",
            equipe_nivel: 2,
            nota_final: 0,
            vitorias: 3,
            empates: 1,
            derrotas: 0,
            posicao: 1,
            formato_chaveamento: "TODOS_CONTRA_TODOS",
          },
          {
            equipe_id: "e2",
            equipe_nome: "Equipe Nivel 3",
            equipe_nivel: 3,
            nota_final: 0,
            vitorias: 2,
            derrotas: 0,
            eliminado_por_nome: null,
            posicao: 1,
            formato_chaveamento: "MATA_MATA",
          },
        ],
      },
      error: undefined,
    } as never);

    renderComponent();

    const tituloNivel2 = await screen.findByText("Nível 2");
    const tabelaNivel2 = tituloNivel2.closest("div")!.querySelector("table")!;
    expect(within(tabelaNivel2).getByText("Pontos")).toBeInTheDocument();
    expect(within(tabelaNivel2).getByText("Empates")).toBeInTheDocument();
    expect(within(tabelaNivel2).queryByText("Eliminado por")).not.toBeInTheDocument();

    const tituloNivel3 = screen.getByText("Nível 3");
    const tabelaNivel3 = tituloNivel3.closest("div")!.querySelector("table")!;
    expect(within(tabelaNivel3).getByText("Eliminado por")).toBeInTheDocument();
    expect(within(tabelaNivel3).queryByText("Pontos")).not.toBeInTheDocument();
  });

  it("modalidade individual (sem formato_chaveamento em nenhum item) mostra coluna Nota", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        modalidade_id: "m1",
        modalidade_nome: "Dança",
        tipo_disputa: "INDIVIDUAL",
        formato_chaveamento: null,
        ranking_liberado: true,
        itens: [
          {
            equipe_id: "e1",
            equipe_nome: "Equipe A",
            equipe_nivel: 2,
            nota_final: 87.5,
            posicao: 1,
            formato_chaveamento: null,
          },
        ],
      },
      error: undefined,
    } as never);

    renderComponent();

    expect(await screen.findByText("Nota")).toBeInTheDocument();
    expect(screen.getByText("87.5")).toBeInTheDocument();
  });
});
