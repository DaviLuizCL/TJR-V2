import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { CombateDashboardPage } from "./CombateDashboardPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(eventoId = "evt-1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/eventos/${eventoId}/combates`]}>
        <Routes>
          <Route path="/eventos/:eventoId/combates" element={<CombateDashboardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CombateDashboardPage", () => {
  it("lista as modalidades de combate com o formato do chaveamento e link para as rodadas", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [
          {
            id: "m1",
            nome: "Sumo de Robos",
            tipo_disputa: "CONFRONTO",
            formato_chaveamento: "MATA_MATA",
          },
        ],
        total: 1,
        page: 1,
        size: 100,
      },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
    expect(await screen.findByText("Mata-Mata")).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /ver rodadas/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/rodadas");

    const linkPontuar = screen.getByRole("link", { name: /^pontuar$/i });
    expect(linkPontuar).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/pontuar");
  });

  it("formato_chaveamento nulo mostra 'Automático por nível', nao 'Sem formato definido'", async () => {
    // formato_chaveamento=null numa modalidade CONFRONTO nao significa mais
    // "sem formato" -- desde o chaveamento por nivel (gerar_chaveamento_confronto),
    // null e o normal: decide sozinho por nivel (<=5 equipes = todos-contra-
    // todos, 6+ = mata-mata). "Sem formato definido" sugeria erro de
    // configuracao, o que confundiu o coordenador ao olhar a tela.
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [
          {
            id: "m1",
            nome: "Sumô",
            tipo_disputa: "CONFRONTO",
            formato_chaveamento: null,
          },
        ],
        total: 1,
        page: 1,
        size: 100,
      },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(await screen.findByText(/autom[aá]tico por n[ií]vel/i)).toBeInTheDocument();
    expect(screen.queryByText(/sem formato definido/i)).not.toBeInTheDocument();
  });

  it("nao mostra modalidades individuais (elas ficam na aba Rodadas)", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [
          { id: "m1", nome: "Resgate", tipo_disputa: "INDIVIDUAL", formato_chaveamento: null },
          {
            id: "m2",
            nome: "Sumo de Robos",
            tipo_disputa: "CONFRONTO",
            formato_chaveamento: "TODOS_CONTRA_TODOS",
          },
        ],
        total: 2,
        page: 1,
        size: 100,
      },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
    expect(screen.queryByText("Resgate")).not.toBeInTheDocument();
  });

  it("mostra mensagem quando nao ha modalidade de combate cadastrada", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 100 },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(
      await screen.findByText(/nenhuma modalidade de combate cadastrada/i),
    ).toBeInTheDocument();
  });
});
