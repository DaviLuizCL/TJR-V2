import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { SequenciaPublicaPage } from "./SequenciaPublicaPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
}));

function equipe(nome: string, posicao: number, extra: Record<string, unknown> = {}) {
  return {
    nome,
    posicao,
    presente: true,
    rodadas_competidas: [],
    proxima: false,
    equipes_na_frente: null,
    ...extra,
  };
}

const SEQUENCIA = [
  {
    id: "mod-danca",
    nome: "Dança",
    rodadas: [1, 2],
    niveis: [
      {
        nivel: 2,
        equipes: [
          equipe("Alfa", 1, { rodadas_competidas: [1] }),
          equipe("Beta", 2, { presente: false }),
          equipe("Gama", 3, { proxima: true }),
        ],
      },
      { nivel: 3, equipes: [equipe("Delta", 1, { proxima: true })] },
    ],
  },
  {
    id: "mod-resgate",
    nome: "Resgate no Plano",
    rodadas: [1, 2],
    niveis: [{ nivel: 2, equipes: [equipe("Ômega", 1)] }],
  },
];

function mockSequencia(dados: unknown = SEQUENCIA) {
  vi.mocked(api.GET).mockResolvedValue({ data: dados } as never);
}

function renderPage(url = "/sequencia") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/sequencia" element={<SequenciaPublicaPage />} />
          <Route path="/sequencia/:modalidade" element={<SequenciaPublicaPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function linhaDaEquipe(nome: string) {
  return screen.getByText(nome).closest("li") as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SequenciaPublicaPage", () => {
  it("busca a sequencia publica sem precisar de id de evento", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Alfa");
    expect(api.GET).toHaveBeenCalledWith("/api/v1/publico/sequencia");
  });

  it("mostra a primeira modalidade com as equipes na ordem, separadas por nivel", async () => {
    mockSequencia();
    renderPage();

    const nivel2 = await screen.findByRole("region", { name: "Nível 2" });
    const nomes = within(nivel2)
      .getAllByRole("listitem")
      .map((li) => li.querySelector("[data-nome]")?.textContent);
    expect(nomes).toEqual(["Alfa", "Beta", "Gama"]);
    expect(screen.getByRole("region", { name: "Nível 3" })).toBeInTheDocument();
    expect(screen.queryByText("Ômega")).not.toBeInTheDocument();
  });

  it("diz por rodada quem ja competiu e quem falta", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Alfa");
    const alfa = linhaDaEquipe("Alfa");
    expect(within(alfa).getByText("Rodada 1: já competiu")).toBeInTheDocument();
    expect(within(alfa).getByText("Rodada 2: falta competir")).toBeInTheDocument();
  });

  it("resume quantas equipes ja competiram em cada rodada do nivel", async () => {
    mockSequencia();
    renderPage();

    const nivel2 = await screen.findByRole("region", { name: "Nível 2" });
    expect(within(nivel2).getByText("Rodada 1: 1 de 3")).toBeInTheDocument();
    expect(within(nivel2).getByText("Rodada 2: 0 de 3")).toBeInTheDocument();
  });

  it("destaca a proxima equipe e marca a ausente", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Gama");
    expect(within(linhaDaEquipe("Gama")).getByText("Próxima")).toBeInTheDocument();
    expect(within(linhaDaEquipe("Beta")).getByText("Ausente")).toBeInTheDocument();
    expect(within(linhaDaEquipe("Alfa")).queryByText("Próxima")).not.toBeInTheDocument();
  });

  it("diz quantas equipes estao na frente de quem ainda vai competir", async () => {
    mockSequencia([
      {
        id: "mod-danca",
        nome: "Dança",
        rodadas: [1],
        niveis: [
          {
            nivel: 2,
            equipes: [
              equipe("Alfa", 1, { proxima: true, equipes_na_frente: 0 }),
              equipe("Beta", 2, { equipes_na_frente: 1 }),
              equipe("Gama", 3, { equipes_na_frente: 3 }),
              equipe("Delta", 4, { rodadas_competidas: [1] }),
            ],
          },
        ],
      },
    ]);
    renderPage();

    await screen.findByText("Alfa");
    expect(within(linhaDaEquipe("Beta")).getByText("1 equipe na frente")).toBeInTheDocument();
    expect(within(linhaDaEquipe("Gama")).getByText("3 equipes na frente")).toBeInTheDocument();
    expect(within(linhaDaEquipe("Alfa")).queryByText(/na frente/)).not.toBeInTheDocument();
    expect(within(linhaDaEquipe("Delta")).queryByText(/na frente/)).not.toBeInTheDocument();
  });

  it("modalidade desconhecida no link cai na primeira", async () => {
    mockSequencia();
    renderPage("/sequencia/nao-existe");

    expect(await screen.findByText("Alfa")).toBeInTheDocument();
  });

  it("troca de modalidade pela aba", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Alfa");
    await userEvent.click(screen.getByRole("tab", { name: "Resgate no Plano" }));

    expect(screen.getByText("Ômega")).toBeInTheDocument();
    expect(screen.queryByText("Alfa")).not.toBeInTheDocument();
  });

  it("abre direto na modalidade pelo nome simples no link", async () => {
    mockSequencia();
    renderPage("/sequencia/resgate-no-plano");

    expect(await screen.findByText("Ômega")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Resgate no Plano" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("mostra por extenso a rodada ja competida, com check", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Alfa");
    expect(within(linhaDaEquipe("Alfa")).getByText("✓ Rodada 1")).toBeInTheDocument();
    expect(within(linhaDaEquipe("Alfa")).getByText("Rodada 2")).toBeInTheDocument();
  });

  it("filtra pelo nome da equipe, sem diferenciar maiuscula", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Alfa");
    await userEvent.type(screen.getByLabelText("Buscar equipe"), "gam");

    expect(screen.getByText("Gama")).toBeInTheDocument();
    expect(screen.queryByText("Alfa")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Nível 3" })).not.toBeInTheDocument();
  });

  it("avisa quando a busca nao acha nenhuma equipe", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Alfa");
    await userEvent.type(screen.getByLabelText("Buscar equipe"), "zzz");

    expect(screen.getByText("Nenhuma equipe com esse nome nesta modalidade.")).toBeInTheDocument();
  });

  it("avisa quando ainda nao ha modalidade individual", async () => {
    mockSequencia([]);
    renderPage();

    expect(
      await screen.findByText("A sequência de competição ainda não foi divulgada."),
    ).toBeInTheDocument();
  });

  it("nao mostra nota nem ranking", async () => {
    mockSequencia();
    renderPage();

    await screen.findByText("Alfa");
    expect(screen.queryByText(/nota|ranking|pontos/i)).not.toBeInTheDocument();
  });
});
