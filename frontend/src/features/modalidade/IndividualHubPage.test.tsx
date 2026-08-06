import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { IndividualHubPage } from "./IndividualHubPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(caminho = "/eventos/evt-1/individual") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[caminho]}>
        <Routes>
          <Route path="/eventos/:eventoId/individual" element={<IndividualHubPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockResolvedValue({
    data: {
      itens: [{ id: "m1", nome: "Resgate no Plano", qtd_rodadas: 3, tipo_disputa: "INDIVIDUAL" }],
      total: 1,
      page: 1,
      size: 100,
    },
    error: undefined,
  } as never);
});

describe("IndividualHubPage", () => {
  it("mostra a aba Pontuar selecionada por padrao", async () => {
    renderPage();

    const abaPontuar = await screen.findByRole("tab", { name: /pontuar/i });
    expect(abaPontuar).toHaveAttribute("aria-selected", "true");

    const link = await screen.findByRole("link", { name: /^pontuar$/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/pontuar");
  });

  it("troca pra aba Rodadas ao clicar", async () => {
    renderPage();

    await userEvent.click(await screen.findByRole("tab", { name: /^rodadas$/i }));

    const link = await screen.findByRole("link", { name: /ver rodadas/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/rodadas");
  });

  it("troca pra aba Horarios ao clicar", async () => {
    renderPage();

    await userEvent.click(await screen.findByRole("tab", { name: /hor[aá]rios/i }));

    const link = await screen.findByRole("link", { name: /ver hor[aá]rios/i });
    expect(link).toHaveAttribute("href", "/eventos/evt-1/modalidades/m1/horarios");
  });

  it("abre direto na aba indicada pelo parametro ?aba=", async () => {
    renderPage("/eventos/evt-1/individual?aba=horarios");

    const abaHorarios = await screen.findByRole("tab", { name: /hor[aá]rios/i });
    expect(abaHorarios).toHaveAttribute("aria-selected", "true");
  });
});
