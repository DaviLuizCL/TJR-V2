import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { EquipeListPage } from "./EquipeListPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <EquipeListPage />
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

describe("EquipeListPage", () => {
  it("lista as equipes cadastradas com nivel e status", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [
          { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true },
          { id: "eq2", nome: "Equipe Beta", nivel: 3, ativo: false },
        ],
        total: 2,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    const linhaAlpha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const linhaBeta = screen.getByText("Equipe Beta").closest("li")!;

    expect(within(linhaAlpha).getByText(/nivel 2/i)).toBeInTheDocument();
    expect(within(linhaBeta).getByText(/inativa/i)).toBeInTheDocument();
  });

  it("linka para a tela de submissoes da equipe", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    const linha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const link = within(linha).getByRole("link", { name: /submiss(o|õ)es/i });
    expect(link).toHaveAttribute("href", "/equipes/eq1/submissoes");
  });

  it("cria uma equipe pelo formulario", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "nova-equipe", nome: "Equipe Nova", nivel: 1, ativo: true },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "Equipe Nova");
    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "1");
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/equipes",
        expect.objectContaining({ body: { nome: "Equipe Nova", nivel: 1, ativo: true } }),
      ),
    );
  });

  it("BUG-07: nao envia o formulario quando o nome tem so espacos", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "   ");
    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "1");
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    expect(await screen.findByText(/informe o nome da equipe/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("BUG-07: tira espaco das pontas do nome antes de enviar", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "nova-equipe", nome: "Equipe Nova", nivel: 1, ativo: true },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "  Equipe Nova  ");
    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "1");
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/equipes",
        expect.objectContaining({ body: { nome: "Equipe Nova", nivel: 1, ativo: true } }),
      ),
    );
  });

  it("desativa uma equipe ativa", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);
    vi.mocked(api.PATCH).mockResolvedValue({
      data: { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: false },
      error: undefined,
    } as never);

    renderPage();

    const botao = await screen.findByRole("button", { name: /desativar/i });
    await userEvent.click(botao);

    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith(
        "/api/v1/equipes/{equipe_id}",
        expect.objectContaining({
          params: { path: { equipe_id: "eq1" } },
          body: { ativo: false },
        }),
      ),
    );
  });

  it("arbitro nao ve o formulario de criar equipe nem os botoes de editar/ativar", async () => {
    logarComo("ARBITRO");
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.queryByRole("button", { name: /^criar equipe$/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/nome da equipe/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /desativar/i })).not.toBeInTheDocument();
    // leitura continua liberada
    expect(screen.getByRole("link", { name: /submiss/i })).toBeInTheDocument();
  });

  it("secretaria tambem nao ve criar/editar/ativar, so leitura", async () => {
    logarComo("SECRETARIA");
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.queryByRole("button", { name: /^criar equipe$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /desativar/i })).not.toBeInTheDocument();
  });

  it("coordenador continua vendo criar/editar/ativar", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
        total: 1,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.getByRole("button", { name: /^criar equipe$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^editar$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /desativar/i })).toBeInTheDocument();
  });
});
