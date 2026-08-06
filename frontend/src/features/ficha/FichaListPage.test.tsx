import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { FichaListPage } from "./FichaListPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const original = await importOriginal<typeof import("react-router-dom")>();
  return { ...original, useNavigate: () => navigateMock };
});

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() },
  extrairErro: (error: { erro?: { codigo: string; mensagem: string } }) =>
    error?.erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." },
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/fichas"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/fichas"
            element={<FichaListPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FichaListPage", () => {
  it("mostra um slot por nivel aplicavel, com botao de criar quando nao ha ficha", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path.includes("/modalidades/")) {
        return {
          data: {
            id: "mod-1",
            nome: "Sumo de Robos",
            niveis_aplicaveis: [1, 2],
            ficha_unica_entre_niveis: false,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText(/nivel 1/i)).toBeInTheDocument();
    expect(screen.getByText(/nivel 2/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /criar ficha/i })).toHaveLength(2);
  });

  it("mostra um unico slot quando a modalidade usa ficha unica entre niveis", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path.includes("/modalidades/")) {
        return {
          data: {
            id: "mod-1",
            nome: "Danca",
            niveis_aplicaveis: [1, 2, 3, 4],
            ficha_unica_entre_niveis: true,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText(/ficha unica/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /criar ficha/i })).toHaveLength(1);
  });

  it("mostra status e link de editar quando ja existe ficha ativa", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path.includes("/modalidades/")) {
        return {
          data: {
            id: "mod-1",
            nome: "Sumo",
            niveis_aplicaveis: [1],
            ficha_unica_entre_niveis: false,
          },
          error: undefined,
        } as never;
      }
      return {
        data: {
          itens: [{ id: "ficha-1", nivel: 1, versao: 1, status: "RASCUNHO" }],
          total: 1,
          page: 1,
          size: 50,
        },
        error: undefined,
      } as never;
    });

    renderPage();

    expect(await screen.findByText(/rascunho/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /editar/i })).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/fichas/ficha-1/editar",
    );
  });

  it("cria a ficha do nivel e navega para o editor dela", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path.includes("/modalidades/")) {
        return {
          data: {
            id: "mod-1",
            nome: "Sumo",
            niveis_aplicaveis: [1],
            ficha_unica_entre_niveis: false,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "ficha-novo", nivel: 1, versao: 1, status: "RASCUNHO" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /criar ficha/i }));

    expect(navigateMock).toHaveBeenCalledWith(
      "/eventos/evt-1/modalidades/mod-1/fichas/ficha-novo/editar",
    );
  });

  function mockGetComFicha() {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path.includes("/modalidades/")) {
        return {
          data: {
            id: "mod-1",
            nome: "Sumo",
            niveis_aplicaveis: [1],
            ficha_unica_entre_niveis: false,
          },
          error: undefined,
        } as never;
      }
      return {
        data: {
          itens: [{ id: "ficha-1", nivel: 1, versao: 1, status: "RASCUNHO" }],
          total: 1,
          page: 1,
          size: 50,
        },
        error: undefined,
      } as never;
    });
  }

  it("exclui a ficha ao confirmar quando nao ha lancamentos", async () => {
    mockGetComFicha();
    vi.mocked(api.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /excluir/i }));

    expect(api.DELETE).toHaveBeenCalledWith(
      "/api/v1/fichas/{ficha_id}",
      expect.objectContaining({ params: { path: { ficha_id: "ficha-1" } } }),
    );
  });

  it("nao chama a API quando o usuario cancela a confirmacao de exclusao", async () => {
    mockGetComFicha();
    vi.mocked(api.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /excluir/i }));

    expect(api.DELETE).not.toHaveBeenCalled();
  });

  it("oferece depreciar quando a exclusao falha por lancamentos existentes", async () => {
    mockGetComFicha();
    vi.mocked(api.DELETE).mockResolvedValue({
      data: undefined,
      error: {
        erro: {
          codigo: "FICHA_POSSUI_LANCAMENTOS",
          mensagem: "Esta ficha ja tem lancamento registrado.",
        },
      },
    } as never);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "ficha-1", nivel: 1, versao: 1, status: "DEPRECADA" },
      error: undefined,
    } as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /excluir/i }));

    expect(await screen.findByText(/ja tem lancamento registrado/i)).toBeInTheDocument();
    const botaoDepreciar = screen.getByRole("button", { name: /depreciar/i });

    await userEvent.click(botaoDepreciar);

    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/fichas/{ficha_id}/depreciar",
      expect.objectContaining({ params: { path: { ficha_id: "ficha-1" } } }),
    );
  });
});
