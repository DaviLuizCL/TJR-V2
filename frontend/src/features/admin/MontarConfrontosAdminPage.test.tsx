import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { MontarConfrontosAdminPage } from "./MontarConfrontosAdminPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: () => ({ codigo: "X", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/admin/montar-confrontos"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/admin/montar-confrontos"
            element={<MontarConfrontosAdminPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
    if (path === "/api/v1/modalidades") {
      return {
        data: {
          itens: [
            { id: "m-sumo", nome: "Sumô", tipo_disputa: "CONFRONTO" },
            { id: "m-cabo", nome: "Cabo de Guerra", tipo_disputa: "CONFRONTO" },
            { id: "m-danca", nome: "Dança", tipo_disputa: "INDIVIDUAL" },
          ],
          total: 3,
          page: 1,
          size: 100,
        },
      } as never;
    }
    if (path === "/api/v1/equipes") {
      return {
        data: { itens: [{ id: "eq-1", nome: "Robozão", nivel: 3, ativo: true }] },
      } as never;
    }
    if (path === "/api/v1/inscricoes") {
      return { data: { itens: [{ equipe_id: "eq-1", modalidade_id: "m-sumo" }] } } as never;
    }
    if (path === "/api/v1/rodadas") {
      return { data: { itens: [] } } as never;
    }
    return { data: undefined } as never;
  });
});

describe("MontarConfrontosAdminPage", () => {
  it("lista so as modalidades de combate pra escolher", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: /sumô/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cabo de guerra/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /dança/i })).not.toBeInTheDocument();
  });

  it("escolher a modalidade abre a montagem na propria pagina, sem janela por cima", async () => {
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /sumô/i }));

    expect(
      await screen.findByRole("button", { name: /^Robozão/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /sumô/i })).toBeInTheDocument();
  });

  it("da pra voltar e trocar de modalidade", async () => {
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /sumô/i }));
    await userEvent.click(await screen.findByRole("button", { name: /trocar modalidade/i }));

    expect(await screen.findByRole("button", { name: /cabo de guerra/i })).toBeInTheDocument();
  });
});
