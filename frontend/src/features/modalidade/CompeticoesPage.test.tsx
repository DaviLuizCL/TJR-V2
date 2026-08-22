import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useEventoStore } from "../../lib/evento-store";
import { CompeticoesPage } from "./CompeticoesPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(caminho = "/eventos/evt-1/competicoes") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[caminho]}>
        <Routes>
          <Route path="/eventos/:eventoId/competicoes" element={<CompeticoesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useEventoStore.setState({ eventoAtualId: null });
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades") {
      return {
        data: {
          itens: [
            { id: "m1", nome: "Resgate no Plano", tipo_disputa: "INDIVIDUAL" },
            {
              id: "m2",
              nome: "Sumo de Robos",
              tipo_disputa: "CONFRONTO",
              formato_chaveamento: "MATA_MATA",
            },
          ],
          total: 2,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
  });
});

describe("CompeticoesPage", () => {
  it("mostra o titulo Competicoes e abre na aba Individual por padrao", async () => {
    renderPage();

    expect(screen.getByRole("heading", { name: /competi[cç][oõ]es/i })).toBeInTheDocument();
    const abaIndividual = await screen.findByRole("tab", { name: /^individual$/i });
    expect(abaIndividual).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByText("Resgate no Plano")).toBeInTheDocument();
  });

  it("troca pra aba Combate ao clicar, mostrando as modalidades de confronto", async () => {
    renderPage();

    await userEvent.click(await screen.findByRole("tab", { name: /^combate$/i }));

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
  });

  it("abre direto na aba Combate quando ?aba=combate esta na url", async () => {
    renderPage("/eventos/evt-1/competicoes?aba=combate");

    const abaCombate = await screen.findByRole("tab", { name: /^combate$/i });
    expect(abaCombate).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
  });

  it("dentro da aba Individual, ainda da pra clicar em Pontuar pra uma modalidade especifica", async () => {
    renderPage();

    const link = await screen.findByRole("link", { name: /^pontuar$/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/pontuar");
  });

  it("registra o evento visitado como evento atual (senao os links do Header quebram)", async () => {
    renderPage();

    await screen.findByRole("heading", { name: /competi[cç][oõ]es/i });
    expect(useEventoStore.getState().eventoAtualId).toBe("evt-1");
  });
});
