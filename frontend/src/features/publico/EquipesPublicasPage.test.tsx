import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { EquipesPublicasPage } from "./EquipesPublicasPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
}));

const EQUIPES = [
  { nome: "Alfa", nivel: 1, modalidades: ["Corrida de Carros Autônomos"] },
  { nome: "Hefesto Tech", nivel: 3, modalidades: ["Cabo de Guerra", "Dança", "Sumô"] },
  { nome: "Sem Nada", nivel: 3, modalidades: [] },
];

function renderPage() {
  vi.mocked(api.GET).mockResolvedValue({ data: EQUIPES } as never);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/equipes-inscritas"]}>
        <Routes>
          <Route path="/equipes-inscritas" element={<EquipesPublicasPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function cartaoDaEquipe(nome: string) {
  return screen.getByText(nome).closest("li") as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("EquipesPublicasPage", () => {
  it("busca as equipes na rota publica, sem login", async () => {
    renderPage();

    await screen.findByText("Hefesto Tech");
    expect(api.GET).toHaveBeenCalledWith("/api/v1/publico/equipes");
  });

  it("mostra a equipe uma vez so, com todas as modalidades dela", async () => {
    renderPage();

    await screen.findByText("Hefesto Tech");
    expect(screen.getAllByText("Hefesto Tech")).toHaveLength(1);
    const cartao = cartaoDaEquipe("Hefesto Tech");
    expect(within(cartao).getByText("Cabo de Guerra")).toBeInTheDocument();
    expect(within(cartao).getByText("Dança")).toBeInTheDocument();
    expect(within(cartao).getByText("Sumô")).toBeInTheDocument();
    expect(within(cartao).getByText("3 modalidades")).toBeInTheDocument();
  });

  it("separa as equipes por nivel, com nivel 1 como ABSOLUTO", async () => {
    renderPage();

    const absoluto = await screen.findByRole("region", { name: /absoluto/i });
    expect(within(absoluto).getByText("Alfa")).toBeInTheDocument();
    const nivel3 = screen.getByRole("region", { name: /nível 3/i });
    expect(within(nivel3).getByText("Hefesto Tech")).toBeInTheDocument();
    expect(within(nivel3).queryByText("Alfa")).not.toBeInTheDocument();
  });

  it("avisa quando a equipe nao esta em nenhuma modalidade", async () => {
    renderPage();

    await screen.findByText("Sem Nada");
    expect(
      within(cartaoDaEquipe("Sem Nada")).getByText(/nenhuma modalidade/i),
    ).toBeInTheDocument();
  });

  it("busca a equipe pelo nome", async () => {
    renderPage();
    await screen.findByText("Hefesto Tech");

    await userEvent.type(screen.getByLabelText(/buscar equipe/i), "hefesto");

    expect(screen.getByText("Hefesto Tech")).toBeInTheDocument();
    expect(screen.queryByText("Alfa")).not.toBeInTheDocument();
    expect(screen.queryByText("Sem Nada")).not.toBeInTheDocument();
  });

  it("filtra pelas equipes de uma modalidade", async () => {
    renderPage();
    await screen.findByText("Hefesto Tech");

    await userEvent.selectOptions(screen.getByLabelText(/modalidade/i), "Dança");

    expect(screen.getByText("Hefesto Tech")).toBeInTheDocument();
    expect(screen.queryByText("Alfa")).not.toBeInTheDocument();
  });
});
