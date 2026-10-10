import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ResetarChaveamentoAdminPage } from "./ResetarChaveamentoAdminPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: () => ({ codigo: "X", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/admin/resetar-chaveamento"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/admin/resetar-chaveamento"
            element={<ResetarChaveamentoAdminPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockResolvedValue({
    data: {
      itens: [
        { id: "m-sumo", nome: "Sumô", tipo_disputa: "CONFRONTO" },
        { id: "m-danca", nome: "Dança", tipo_disputa: "INDIVIDUAL" },
      ],
      total: 2,
      page: 1,
      size: 100,
    },
  } as never);
  vi.mocked(api.POST).mockResolvedValue({ data: undefined, error: undefined } as never);
});

describe("ResetarChaveamentoAdminPage", () => {
  it("lista so as modalidades de combate", async () => {
    renderPage();

    expect(await screen.findByText("Sumô")).toBeInTheDocument();
    expect(screen.queryByText("Dança")).not.toBeInTheDocument();
  });

  it("abre a confirmacao com justificativa e reseta a modalidade escolhida", async () => {
    renderPage();

    const linha = (await screen.findByText("Sumô")).closest("li")!;
    await userEvent.click(within(linha).getByRole("button", { name: /resetar/i }));
    const dialogo = screen.getByRole("dialog", { name: /resetar chaveamento/i });
    await userEvent.type(within(dialogo).getByLabelText(/justificativa/i), "montei errado");
    await userEvent.click(within(dialogo).getByRole("button", { name: /confirmar reset/i }));

    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/modalidades/{modalidade_id}/chaveamento/reset",
      { params: { path: { modalidade_id: "m-sumo" } }, body: { justificativa: "montei errado" } },
    );
    expect(await screen.findByText(/chaveamento de sumô apagado/i)).toBeInTheDocument();
  });
});
