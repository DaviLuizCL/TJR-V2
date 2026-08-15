import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { EventoSelectPage } from "./EventoSelectPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const original = await importOriginal<typeof import("react-router-dom")>();
  return { ...original, useNavigate: () => navigateMock };
});

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
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
        itens: [
          { id: "e1", nome: "TJR 2026", ano: 2026, status: "RASCUNHO" },
          { id: "e2", nome: "TJR 2025", ano: 2025, status: "ENCERRADO" },
        ],
        total: 2,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByText("TJR 2026")).toBeInTheDocument();
    expect(screen.getByText("TJR 2025")).toBeInTheDocument();
  });

  it("cria um evento novo pelo formulario e navega para as modalidades dele", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "novo-evento", nome: "TJR 2027", ano: 2027, status: "RASCUNHO" },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByRole("button", { name: /criar evento/i });

    await userEvent.type(screen.getByLabelText(/nome do evento/i), "TJR 2027");
    await userEvent.type(screen.getByLabelText(/^ano/i), "2027");
    await userEvent.type(screen.getByLabelText(/data de inicio/i), "2027-03-10");
    await userEvent.type(screen.getByLabelText(/data de fim/i), "2027-03-12");
    await userEvent.click(screen.getByRole("button", { name: /criar evento/i }));

    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith("/eventos/novo-evento/modalidades"),
    );
  });

  it("arbitro nao ve o formulario de criar evento, so a lista", async () => {
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

  it("secretaria tambem nao ve o formulario de criar evento", async () => {
    logarComo("SECRETARIA");
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByText(/nenhum evento cadastrado/i);
    expect(screen.queryByRole("button", { name: /criar evento/i })).not.toBeInTheDocument();
  });

  it("coordenador continua vendo o formulario de criar evento", async () => {
    logarComo("COORDENADOR");
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByRole("button", { name: /criar evento/i })).toBeInTheDocument();
  });
});
