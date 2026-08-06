import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { FichaDashboardPage } from "./FichaDashboardPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(eventoId = "evt-1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/eventos/${eventoId}/fichas`]}>
        <Routes>
          <Route path="/eventos/:eventoId/fichas" element={<FichaDashboardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FichaDashboardPage", () => {
  it("lista as modalidades do evento com o status das fichas e link para cada uma", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Sumo de Robos", tipo_disputa: "CONFRONTO" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas") {
        return {
          data: { itens: [{ id: "f1", status: "PUBLICADA" }], total: 1, page: 1, size: 50 },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage("evt-1");

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
    expect(await screen.findByText(/publicada/i)).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /ver fichas/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/fichas");
  });

  it("mostra mensagem quando o evento nao tem modalidades ainda", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 100 },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(await screen.findByText(/nenhuma modalidade cadastrada/i)).toBeInTheDocument();
  });
});
