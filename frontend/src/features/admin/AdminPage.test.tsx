import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useEventoStore } from "../../lib/evento-store";
import { AdminPage } from "./AdminPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: (e: { erro?: { mensagem?: string } }) => ({
    codigo: "X",
    mensagem: e?.erro?.mensagem ?? "Ocorreu um erro inesperado.",
  }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/admin"]}>
        <Routes>
          <Route path="/eventos/:eventoId/admin" element={<AdminPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useEventoStore.setState({ eventoAtualId: null });
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
});

describe("AdminPage", () => {
  it.each([
    [/checklist do dia/i, "/eventos/evt-1/admin/checklist"],
    [/corrigir pontua/i, "/eventos/evt-1/admin/corrigir"],
    [/ju[ií]zes e senhas/i, "/usuarios"],
    [/importar equipes/i, "/eventos/evt-1/admin/importar"],
    [/equipes e presen/i, "/equipes"],
    [/sequ[eê]ncia de competi/i, "/eventos/evt-1/competicoes?aba=individual&sub=ordem"],
    [/fichas de pontua/i, "/eventos/evt-1/fichas"],
    [/resetar chaveamento/i, "/eventos/evt-1/admin/resetar-chaveamento"],
  ])("cartao %s leva pra %s", (nome, href) => {
    renderPage();

    expect(screen.getByRole("link", { name: nome })).toHaveAttribute("href", href);
  });

  it("guarda o evento atual pros outros links do menu", () => {
    renderPage();

    expect(useEventoStore.getState().eventoAtualId).toBe("evt-1");
  });

  it("baixar backup chama a API como arquivo binario", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: new Blob(["x"]), error: undefined } as never);
    renderPage();

    await userEvent.click(screen.getByRole("button", { name: /baixar backup/i }));

    expect(api.GET).toHaveBeenCalledWith("/api/v1/admin/backup", { parseAs: "blob" });
    expect(await screen.findByText(/backup baixado/i)).toBeInTheDocument();
  });

  it("mostra erro se o backup falhar", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: undefined,
      error: { erro: { mensagem: "Nao foi possivel gerar o backup agora." } },
    } as never);
    renderPage();

    await userEvent.click(screen.getByRole("button", { name: /baixar backup/i }));

    expect(await screen.findByText(/nao foi possivel gerar o backup/i)).toBeInTheDocument();
  });

  it("baixar relatorio geral chama a rota do PDF do evento", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: new Blob(["x"]), error: undefined } as never);
    renderPage();

    await userEvent.click(screen.getByRole("button", { name: /relat[oó]rio geral/i }));

    expect(api.GET).toHaveBeenCalledWith(
      "/api/v1/ranking/eventos/{evento_id}/relatorio-auditoria.pdf",
      { params: { path: { evento_id: "evt-1" } }, parseAs: "blob" },
    );
  });
});
