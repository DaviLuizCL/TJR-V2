import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { EventoSelectPage } from "./EventoSelectPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <EventoSelectPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function logarComo(papel: string) {
  useAuthStore.setState({
    accessToken: "tok",
    refreshToken: "tok",
    usuario: { id: "u1", nome: "Usuario Teste", email: "user@tjr.app", papel },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  logarComo("COORDENADOR");
});

describe("EventoSelectPage", () => {
  it("lista os eventos existentes", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "e1", nome: "TJR 2026", ano: 2026, status: "RASCUNHO" }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByText("TJR 2026")).toBeInTheDocument();
  });

  it("nao mostra nenhum formulario de criar evento, nem pro coordenador", async () => {
    logarComo("COORDENADOR");
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByText(/nenhum evento cadastrado/i);
    expect(screen.queryByRole("button", { name: /criar evento/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/nome do evento/i)).not.toBeInTheDocument();
  });

  it("arbitro tambem nao ve nenhum formulario de criar evento", async () => {
    logarComo("ARBITRO");
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "e1", nome: "TJR 2026", ano: 2026, status: "RASCUNHO" }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByText("TJR 2026")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /criar evento/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/nome do evento/i)).not.toBeInTheDocument();
  });

  it("BUG-04: arbitro clicando num evento vai direto pra Individual, nao pra area administrativa de Modalidades", async () => {
    logarComo("ARBITRO");
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "e1", nome: "TJR 2026", ano: 2026, status: "RASCUNHO" }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    const link = await screen.findByRole("link", { name: /tjr 2026/i });
    expect(link).toHaveAttribute("href", "/eventos/e1/competicoes");
  });

  it("coordenador clicando num evento tambem vai direto pra Competicoes", async () => {
    logarComo("COORDENADOR");
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "e1", nome: "TJR 2026", ano: 2026, status: "RASCUNHO" }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    const link = await screen.findByRole("link", { name: /tjr 2026/i });
    expect(link).toHaveAttribute("href", "/eventos/e1/competicoes");
  });
});
