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

// Mocka o GET generico do client (usado tanto pra /equipes quanto pra
// /modalidades, que alimenta o filtro) roteando pelo path -- sem isso os dois
// hooks de useQuery da pagina recebiam o mesmo payload de equipes, duplicando
// nomes na tela (equipe vira tambem opcao do <select> de modalidade) e
// quebrando os testes que buscam por texto unico.
function mockGetEquipes(
  equipesPayload: unknown,
  modalidadesPayload: unknown = { itens: [], total: 0, page: 1, size: 200 },
  inscricoesPayload: unknown = { itens: [], total: 0, page: 1, size: 1000 },
) {
  vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
    if (path === "/api/v1/modalidades") {
      return { data: modalidadesPayload, error: undefined } as never;
    }
    if (path === "/api/v1/equipes") {
      return { data: equipesPayload, error: undefined } as never;
    }
    if (path === "/api/v1/inscricoes") {
      return { data: inscricoesPayload, error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  logarComo("COORDENADOR");
});

describe("EquipeListPage", () => {
  it("lista as equipes cadastradas com nivel e status", async () => {
    mockGetEquipes({
      itens: [
        { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true },
        { id: "eq2", nome: "Equipe Beta", nivel: 3, ativo: false },
      ],
      total: 2,
      page: 1,
      size: 50,
    });

    renderPage();

    const linhaAlpha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const linhaBeta = screen.getByText("Equipe Beta").closest("li")!;

    expect(within(linhaAlpha).getByText(/nível 2/i)).toBeInTheDocument();
    expect(within(linhaBeta).getByText(/inativa/i)).toBeInTheDocument();
  });

  it("mostra as modalidades em que cada equipe esta inscrita", async () => {
    mockGetEquipes(
      {
        itens: [
          { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true },
          { id: "eq2", nome: "Equipe Beta", nivel: 3, ativo: true },
        ],
        total: 2,
        page: 1,
        size: 50,
      },
      {
        itens: [
          { id: "mod-1", nome: "Sumô" },
          { id: "mod-2", nome: "Cabo de Guerra" },
        ],
        total: 2,
        page: 1,
        size: 200,
      },
      {
        itens: [
          { id: "ins-1", equipe_id: "eq1", modalidade_id: "mod-1" },
          { id: "ins-2", equipe_id: "eq1", modalidade_id: "mod-2" },
        ],
        total: 2,
        page: 1,
        size: 1000,
      },
    );

    renderPage();

    const linhaAlpha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const linhaBeta = screen.getByText("Equipe Beta").closest("li")!;

    expect(within(linhaAlpha).getByText(/Sumô, Cabo de Guerra/)).toBeInTheDocument();
    expect(within(linhaBeta).getByText(/nenhuma modalidade/i)).toBeInTheDocument();
  });

  it("filtra equipes por modalidade", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: unknown, options?: unknown) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "mod-1", nome: "Sumo" },
              { id: "mod-2", nome: "Danca" },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        const query = (options as { params?: { query?: Record<string, unknown> } })?.params
          ?.query;
        if (query?.modalidade_id === "mod-1") {
          return {
            data: {
              itens: [{ id: "eq1", nome: "Equipe Sumo", nivel: 1, ativo: true }],
              total: 1,
              page: 1,
              size: 100,
            },
            error: undefined,
          } as never;
        }
        return {
          data: {
            itens: [
              { id: "eq1", nome: "Equipe Sumo", nivel: 1, ativo: true },
              { id: "eq2", nome: "Equipe Danca", nivel: 1, ativo: true },
            ],
            total: 2,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await screen.findByText("Equipe Sumo");
    expect(screen.getByText("Equipe Danca")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/filtrar por modalidade/i), "mod-1");

    await waitFor(() => expect(screen.queryByText("Equipe Danca")).not.toBeInTheDocument());
    expect(screen.getByText("Equipe Sumo")).toBeInTheDocument();
  });

  it("linka para a tela de submissoes da equipe", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

    renderPage();

    const linha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const link = within(linha).getByRole("link", { name: /submiss(o|õ)es/i });
    expect(link).toHaveAttribute("href", "/equipes/eq1/submissoes");
  });

  it("cria uma equipe pelo formulario", async () => {
    mockGetEquipes({ itens: [], total: 0, page: 1, size: 50 });
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
    mockGetEquipes({ itens: [], total: 0, page: 1, size: 50 });

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "   ");
    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "1");
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    expect(await screen.findByText(/informe o nome da equipe/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("BUG-07: tira espaco das pontas do nome antes de enviar", async () => {
    mockGetEquipes({ itens: [], total: 0, page: 1, size: 50 });
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
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });
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
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

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
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.queryByRole("button", { name: /^criar equipe$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /desativar/i })).not.toBeInTheDocument();
  });

  it("coordenador continua vendo criar/editar/ativar", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.getByRole("button", { name: /^criar equipe$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^editar$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /desativar/i })).toBeInTheDocument();
  });
});
