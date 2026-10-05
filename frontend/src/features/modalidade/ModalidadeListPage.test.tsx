import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { useEventoStore } from "../../lib/evento-store";
import { ModalidadeListPage } from "./ModalidadeListPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(eventoId = "evt-1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/eventos/${eventoId}/modalidades`]}>
        <Routes>
          <Route path="/eventos/:eventoId/modalidades" element={<ModalidadeListPage />} />
        </Routes>
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
  useEventoStore.setState({ eventoAtualId: null });
  logarComo("COORDENADOR");
});

describe("ModalidadeListPage", () => {
  it("lista as modalidades do evento com o status e o link para criar uma nova", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "m1", nome: "Sumo de Robos", tipo_disputa: "CONFRONTO", status: "RASCUNHO" },
            ],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /nova modalidade/i })).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/novo",
    );
  });

  it("mostra 'ficha nao criada' quando a modalidade nao tem nenhuma ficha", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Danca", tipo_disputa: "INDIVIDUAL", status: "RASCUNHO" }],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    expect(await screen.findByText(/ficha: nao criada/i)).toBeInTheDocument();
  });

  it("mostra 'ficha publicada' quando todas as fichas ativas estao publicadas", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Danca", tipo_disputa: "INDIVIDUAL", status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return {
        data: { itens: [{ id: "f1", status: "PUBLICADA" }], total: 1, page: 1, size: 50 },
        error: undefined,
      } as never;
    });

    renderPage();

    expect(await screen.findByText(/ficha: publicada/i)).toBeInTheDocument();
  });

  it("cada modalidade linka para a tela de edicao dela", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Sumo", tipo_disputa: "CONFRONTO", status: "RASCUNHO" }],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    const link = await screen.findByRole("link", { name: /sumo/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/editar");
  });

  it("linka para o cadastro global de equipes", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    const link = await screen.findByRole("link", { name: /gerenciar equipes/i });
    expect(link).toHaveAttribute("href", "/equipes");
  });

  it("cada modalidade linka para inscricoes e rodadas dela", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Sumo", tipo_disputa: "CONFRONTO", status: "RASCUNHO" }],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    const linkInscricoes = await screen.findByRole("link", { name: /inscricoes/i });
    expect(linkInscricoes).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/inscricoes");

    const linkRodadas = screen.getByRole("link", { name: /rodadas/i });
    expect(linkRodadas).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/rodadas");
  });

  it("registra o evento visitado como evento atual", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage("evt-9");

    await waitFor(() => expect(useEventoStore.getState().eventoAtualId).toBe("evt-9"));
  });

  it("coordenador baixa o relatorio geral de auditoria em pdf do evento", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Sumo", tipo_disputa: "CONFRONTO", status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/ranking/eventos/{evento_id}/relatorio-auditoria.pdf") {
        return {
          data: new Blob(["%PDF-conteudo"], { type: "application/pdf" }),
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });
    const criarObjectUrl = vi.fn().mockReturnValue("blob:fake-url");
    const revogarObjectUrl = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL: criarObjectUrl, revokeObjectURL: revogarObjectUrl });

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /baixar relat[oó]rio geral/i }));

    await waitFor(() =>
      expect(api.GET).toHaveBeenCalledWith(
        "/api/v1/ranking/eventos/{evento_id}/relatorio-auditoria.pdf",
        expect.objectContaining({
          params: { path: { evento_id: "evt-1" } },
          parseAs: "blob",
        }),
      ),
    );
    expect(criarObjectUrl).toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it("botao 'Baixar relatorio geral' nao aparece sem modalidade cadastrada", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await waitFor(() => expect(screen.getByText(/nenhuma modalidade cadastrada/i)).toBeInTheDocument());
    expect(
      screen.queryByRole("button", { name: /baixar relat[oó]rio geral/i }),
    ).not.toBeInTheDocument();
  });

  it("clicar em 'Abrir evento' abre o modal com uma linha por modalidade individual", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "m1", nome: "Sumo", tipo_disputa: "CONFRONTO", status: "RASCUNHO" },
              { id: "m2", nome: "Danca", tipo_disputa: "INDIVIDUAL", status: "RASCUNHO" },
            ],
            total: 2,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();
    await screen.findByText("Sumo");
    await userEvent.click(screen.getByRole("button", { name: /abrir evento/i }));

    const modal = await screen.findByRole("dialog", { name: /abrir evento/i });
    expect(within(modal).queryByLabelText("Sumo")).not.toBeInTheDocument();
    expect(within(modal).getByLabelText("Danca")).toBeInTheDocument();
  });

  it("botao 'Abrir evento' nao aparece sem modalidade cadastrada", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await waitFor(() => expect(screen.getByText(/nenhuma modalidade cadastrada/i)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /abrir evento/i })).not.toBeInTheDocument();
  });

  it("arbitro nao ve 'Gerenciar equipes' nem 'Nova modalidade'", async () => {
    logarComo("ARBITRO");
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await waitFor(() => expect(screen.getByText(/nenhuma modalidade cadastrada/i)).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /gerenciar equipes/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /nova modalidade/i })).not.toBeInTheDocument();
  });

  it("secretaria tambem nao ve 'Gerenciar equipes' nem 'Nova modalidade'", async () => {
    logarComo("SECRETARIA");
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await waitFor(() => expect(screen.getByText(/nenhuma modalidade cadastrada/i)).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /gerenciar equipes/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /nova modalidade/i })).not.toBeInTheDocument();
  });

  it("coordenador continua vendo 'Gerenciar equipes' e 'Nova modalidade'", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 50 },
      error: undefined,
    } as never);

    renderPage();

    await waitFor(() => expect(screen.getByText(/nenhuma modalidade cadastrada/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /gerenciar equipes/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /nova modalidade/i })).toBeInTheDocument();
  });

  it("arbitro nao ve o botao 'Abrir evento' mesmo com modalidade cadastrada", async () => {
    logarComo("ARBITRO");
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Sumo", tipo_disputa: "CONFRONTO", status: "RASCUNHO" }],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    await screen.findByText("Sumo");
    expect(screen.queryByRole("button", { name: /abrir evento/i })).not.toBeInTheDocument();
  });

  it("secretaria tambem nao ve o botao 'Abrir evento'", async () => {
    logarComo("SECRETARIA");
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [{ id: "m1", nome: "Sumo", tipo_disputa: "CONFRONTO", status: "RASCUNHO" }],
            total: 1,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage();

    await screen.findByText("Sumo");
    expect(screen.queryByRole("button", { name: /abrir evento/i })).not.toBeInTheDocument();
  });
});
