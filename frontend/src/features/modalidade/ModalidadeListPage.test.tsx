import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useEventoStore } from "../../lib/evento-store";
import { ModalidadeListPage } from "./ModalidadeListPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), PATCH: vi.fn() },
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

beforeEach(() => {
  vi.clearAllMocks();
  useEventoStore.setState({ eventoAtualId: null });
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

  it("mostra 'Liberar ranking' quando o ranking ainda nao foi liberado e libera ao clicar", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              {
                id: "m1",
                nome: "Sumo",
                tipo_disputa: "CONFRONTO",
                status: "PUBLICADA",
                ranking_liberado: false,
              },
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
    vi.mocked(api.PATCH).mockResolvedValue({ data: {}, error: undefined } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /liberar ranking/i }));

    expect(api.PATCH).toHaveBeenCalledWith(
      "/api/v1/modalidades/{modalidade_id}",
      expect.objectContaining({
        params: { path: { modalidade_id: "m1" } },
        body: { ranking_liberado: true },
      }),
    );
  });

  it("mostra 'Ocultar ranking' quando o ranking ja esta liberado", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              {
                id: "m1",
                nome: "Sumo",
                tipo_disputa: "CONFRONTO",
                status: "PUBLICADA",
                ranking_liberado: true,
              },
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
    vi.mocked(api.PATCH).mockResolvedValue({ data: {}, error: undefined } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /ocultar ranking/i }));

    expect(api.PATCH).toHaveBeenCalledWith(
      "/api/v1/modalidades/{modalidade_id}",
      expect.objectContaining({
        params: { path: { modalidade_id: "m1" } },
        body: { ranking_liberado: false },
      }),
    );
  });
});
