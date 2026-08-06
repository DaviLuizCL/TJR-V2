import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PontuarRoutePage } from "./PontuarRoutePage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

vi.mock("./PontuarPage", () => ({
  PontuarPage: () => <div>PONTUAR INDIVIDUAL</div>,
}));

vi.mock("./PontuarCombatePage", () => ({
  PontuarCombatePage: () => <div>PONTUAR COMBATE</div>,
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/pontuar"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/pontuar"
            element={<PontuarRoutePage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PontuarRoutePage", () => {
  it("renderiza PontuarPage para modalidade INDIVIDUAL", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { id: "mod-1", tipo_disputa: "INDIVIDUAL" },
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByText("PONTUAR INDIVIDUAL")).toBeInTheDocument();
    expect(screen.queryByText("PONTUAR COMBATE")).not.toBeInTheDocument();
  });

  it("renderiza PontuarCombatePage para modalidade CONFRONTO", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { id: "mod-1", tipo_disputa: "CONFRONTO" },
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByText("PONTUAR COMBATE")).toBeInTheDocument();
    expect(screen.queryByText("PONTUAR INDIVIDUAL")).not.toBeInTheDocument();
  });
});
