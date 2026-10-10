import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ChecklistPage } from "./ChecklistPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  extrairErro: () => ({ codigo: "X", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/admin/checklist"]}>
        <Routes>
          <Route path="/eventos/:eventoId/admin/checklist" element={<ChecklistPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockChecklist(checklist: unknown) {
  vi.mocked(api.GET).mockResolvedValue({ data: checklist, error: undefined } as never);
}

const TUDO_OK = {
  gerais: [
    { codigo: "JUIZES", ok: true, mensagem: "16 juízes cadastrados." },
    { codigo: "NOTAS_PENDENTES", ok: true, mensagem: "Nenhuma nota esperando confirmação." },
  ],
  modalidades: [
    {
      modalidade_id: "mod-1",
      nome: "Dança",
      tipo_disputa: "INDIVIDUAL",
      itens: [{ codigo: "FICHA", ok: true, mensagem: "Ficha de pontuação publicada." }],
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ChecklistPage", () => {
  it("busca o checklist do evento da URL", async () => {
    mockChecklist(TUDO_OK);

    renderPage();

    await screen.findByText("Dança");
    expect(api.GET).toHaveBeenCalledWith("/api/v1/admin/checklist", {
      params: { query: { evento_id: "evt-1" } },
    });
  });

  it("mostra 'tudo pronto' quando nao ha pendencia", async () => {
    mockChecklist(TUDO_OK);

    renderPage();

    expect(await screen.findByText(/tudo pronto/i)).toBeInTheDocument();
  });

  it("conta as pendencias no topo", async () => {
    mockChecklist({
      ...TUDO_OK,
      modalidades: [
        {
          modalidade_id: "mod-1",
          nome: "Dança",
          tipo_disputa: "INDIVIDUAL",
          itens: [
            { codigo: "RODADAS", ok: false, mensagem: "0 de 2 rodadas criadas." },
            { codigo: "ORDEM", ok: false, mensagem: "Falta sortear a ordem." },
          ],
        },
      ],
    });

    renderPage();

    expect(await screen.findByText(/2 pendências/i)).toBeInTheDocument();
  });

  it("item pendente tem botao Resolver que leva pra tela certa", async () => {
    mockChecklist({
      ...TUDO_OK,
      modalidades: [
        {
          modalidade_id: "mod-1",
          nome: "Dança",
          tipo_disputa: "INDIVIDUAL",
          itens: [{ codigo: "ORDEM", ok: false, mensagem: "Falta sortear a ordem." }],
        },
      ],
    });

    renderPage();

    const item = (await screen.findByText("Falta sortear a ordem.")).closest("li")!;
    expect(within(item).getByRole("link", { name: /resolver/i })).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/ordem",
    );
  });

  it("item ok nao tem botao Resolver", async () => {
    mockChecklist(TUDO_OK);

    renderPage();

    const item = (await screen.findByText("Ficha de pontuação publicada.")).closest("li")!;
    expect(within(item).queryByRole("link")).toBeNull();
  });

  it("notas pendentes de confirmacao levam pra tela de corrigir pontuacao", async () => {
    mockChecklist({
      ...TUDO_OK,
      gerais: [
        { codigo: "JUIZES", ok: true, mensagem: "16 juízes cadastrados." },
        { codigo: "NOTAS_PENDENTES", ok: false, mensagem: "2 notas registradas esperando." },
      ],
    });

    renderPage();

    const item = (await screen.findByText("2 notas registradas esperando.")).closest("li")!;
    expect(within(item).getByRole("link", { name: /resolver/i })).toHaveAttribute(
      "href",
      "/eventos/evt-1/admin/corrigir",
    );
  });
});
