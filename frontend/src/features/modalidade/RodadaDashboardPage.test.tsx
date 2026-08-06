import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RodadaDashboardPage } from "./RodadaDashboardPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(eventoId = "evt-1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/eventos/${eventoId}/rodadas`]}>
        <Routes>
          <Route path="/eventos/:eventoId/rodadas" element={<RodadaDashboardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RodadaDashboardPage", () => {
  it("lista as modalidades individuais do evento com o progresso de rodadas e link para cada uma", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "m1", nome: "Sumo de Robos", qtd_rodadas: 3, tipo_disputa: "INDIVIDUAL" },
            ],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: {
            itens: [{ id: "r1" }, { id: "r2" }],
            total: 2,
            page: 1,
            size: 50,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage("evt-1");

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
    expect(await screen.findByText("2/3 rodadas criadas")).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /ver rodadas/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/rodadas");
  });

  it("nao mostra modalidades de confronto (elas ficam na aba Combates)", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "m1", nome: "Resgate", qtd_rodadas: 3, tipo_disputa: "INDIVIDUAL" },
              { id: "m2", nome: "Sumo de Robos", qtd_rodadas: 3, tipo_disputa: "CONFRONTO" },
            ],
            total: 2,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });

    renderPage("evt-1");

    expect(await screen.findByText("Resgate")).toBeInTheDocument();
    expect(screen.queryByText("Sumo de Robos")).not.toBeInTheDocument();
  });

  it("nao quebra quando o cache global ja tem uma lista de rodadas sob a mesma chave (ex.: usuario veio da tela de rodadas da modalidade)", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "m1", nome: "Sumo de Robos", qtd_rodadas: 3, tipo_disputa: "INDIVIDUAL" },
            ],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas") {
        return {
          data: { itens: [{ id: "r1" }, { id: "r2" }], total: 2, page: 1, size: 50 },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    // Simula a RodadaListPage tendo cacheado uma lista de rodadas (nao uma contagem)
    // sob a mesma chave que a RodadaDashboardPage usa para o total.
    queryClient.setQueryData(["rodadas", "m1"], [
      { id: "r1", numero: 1, status: "AGENDADA" },
      { id: "r2", numero: 2, status: "AGENDADA" },
    ]);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/eventos/evt-1/rodadas"]}>
          <Routes>
            <Route path="/eventos/:eventoId/rodadas" element={<RodadaDashboardPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
    expect(await screen.findByText("2/3 rodadas criadas")).toBeInTheDocument();
  });

  it("mostra mensagem quando o evento nao tem modalidades individuais ainda", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { itens: [], total: 0, page: 1, size: 100 },
      error: undefined,
    } as never);

    renderPage("evt-1");

    expect(await screen.findByText(/nenhuma modalidade individual cadastrada/i)).toBeInTheDocument();
  });
});
