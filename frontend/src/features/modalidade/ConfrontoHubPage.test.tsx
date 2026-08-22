import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ConfrontoHubPage } from "./ConfrontoHubPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(caminho = "/eventos/evt-1/combates") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[caminho]}>
        <Routes>
          <Route path="/eventos/:eventoId/combates" element={<ConfrontoHubPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades") {
      return {
        data: {
          itens: [
            {
              id: "m1",
              nome: "Sumo de Robos",
              tipo_disputa: "CONFRONTO",
              formato_chaveamento: "MATA_MATA",
            },
          ],
          total: 1,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/rodadas") {
      return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
    }
    if (path === "/api/v1/equipes") {
      return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
});

describe("ConfrontoHubPage", () => {
  it("mostra a aba Modalidades selecionada por padrao", async () => {
    renderPage();

    const abaModalidades = await screen.findByRole("tab", { name: /modalidades/i });
    expect(abaModalidades).toHaveAttribute("aria-selected", "true");

    expect(await screen.findByText("Sumo de Robos")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /^pontuar$/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/pontuar");
  });

  it("troca pra aba Chaveamento ao clicar", async () => {
    renderPage();

    await userEvent.click(await screen.findByRole("tab", { name: /chaveamento/i }));

    const seletor = await screen.findByLabelText(/modalidade/i);
    expect(seletor).toBeInTheDocument();
  });

  it("abre direto na aba indicada pelo parametro ?sub=", async () => {
    renderPage("/eventos/evt-1/combates?sub=chaveamento");

    const abaChaveamento = await screen.findByRole("tab", { name: /chaveamento/i });
    expect(abaChaveamento).toHaveAttribute("aria-selected", "true");
  });
});
