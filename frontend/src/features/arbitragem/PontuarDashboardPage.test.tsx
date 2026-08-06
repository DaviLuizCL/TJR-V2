import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PontuarDashboardPage } from "./PontuarDashboardPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(eventoId = "evt-1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/eventos/${eventoId}/pontuar`]}>
        <Routes>
          <Route path="/eventos/:eventoId/pontuar" element={<PontuarDashboardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PontuarDashboardPage", () => {
  it("lista so as modalidades individuais do evento com link para pontuar cada uma", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [
          { id: "m1", nome: "Resgate no Plano", tipo_disputa: "INDIVIDUAL" },
          { id: "m2", nome: "Sumo de Robos", tipo_disputa: "CONFRONTO" },
        ],
        total: 2,
        page: 1,
        size: 100,
      },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(await screen.findByText("Resgate no Plano")).toBeInTheDocument();
    expect(screen.queryByText("Sumo de Robos")).not.toBeInTheDocument();

    const link = screen.getByRole("link", { name: /pontuar/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/pontuar");
  });

  it("mostra mensagem quando nao ha modalidade individual ainda", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 100 },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(await screen.findByText(/nenhuma modalidade individual cadastrada/i)).toBeInTheDocument();
  });
});
