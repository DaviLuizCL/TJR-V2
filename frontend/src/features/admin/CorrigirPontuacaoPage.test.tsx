import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { CorrigirPontuacaoPage } from "./CorrigirPontuacaoPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: (e: { erro?: { mensagem?: string } }) => ({
    codigo: "X",
    mensagem: e?.erro?.mensagem ?? "Ocorreu um erro inesperado.",
  }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/admin/corrigir"]}>
        <Routes>
          <Route path="/eventos/:eventoId/admin/corrigir" element={<CorrigirPontuacaoPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const LANCAMENTOS = [
  {
    id: "l-1",
    modalidade_nome: "Dança",
    nivel: 2,
    equipe_nome: "Robotech",
    rodada_numero: 1,
    tentativa: 1,
    partida_id: null,
    responsavel_nome: "Juiz Ana",
    horario_submissao: "2026-10-10T12:00:00Z",
    status: "CONFIRMADO",
    total: 42,
    itens: [],
  },
  {
    id: "l-2",
    modalidade_nome: "Dança",
    nivel: 2,
    equipe_nome: "Megabots",
    rodada_numero: 1,
    tentativa: 1,
    partida_id: null,
    responsavel_nome: "Juiz Ana",
    horario_submissao: "2026-10-10T12:05:00Z",
    status: "PENDENTE",
    total: 10,
    itens: [],
  },
  {
    id: "l-3",
    modalidade_nome: "Dança",
    nivel: 2,
    equipe_nome: "Antigos",
    rodada_numero: 1,
    tentativa: 1,
    partida_id: null,
    responsavel_nome: "Juiz Ana",
    horario_submissao: "2026-10-10T11:00:00Z",
    status: "ANULADO",
    total: 5,
    itens: [],
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades") {
      return {
        data: { itens: [{ id: "mod-1", nome: "Dança" }], total: 1, page: 1, size: 100 },
      } as never;
    }
    if (path === "/api/v1/lancamentos/auditoria") {
      return {
        data: { itens: LANCAMENTOS, total: LANCAMENTOS.length, page: 1, size: 200 },
      } as never;
    }
    return { data: undefined } as never;
  });
  vi.mocked(api.POST).mockResolvedValue({ data: { status: "ANULADO" }, error: undefined } as never);
});

async function escolherModalidade() {
  await screen.findByRole("option", { name: "Dança" });
  await userEvent.selectOptions(screen.getByLabelText(/modalidade/i), "mod-1");
}

function linha(nomeEquipe: string): HTMLElement {
  return screen.getByText(nomeEquipe).closest("li")!;
}

describe("CorrigirPontuacaoPage", () => {
  it("lista as notas lancadas da modalidade escolhida", async () => {
    renderPage();
    await escolherModalidade();

    expect(await screen.findByText("Robotech")).toBeInTheDocument();
    expect(screen.getByText("Megabots")).toBeInTheDocument();
    expect(api.GET).toHaveBeenCalledWith(
      "/api/v1/lancamentos/auditoria",
      expect.objectContaining({
        params: { query: expect.objectContaining({ modalidade_id: "mod-1" }) },
      }),
    );
  });

  it("filtra a lista pelo nome da equipe digitado", async () => {
    renderPage();
    await escolherModalidade();
    await screen.findByText("Robotech");

    await userEvent.type(screen.getByLabelText(/buscar equipe/i), "mega");

    expect(screen.queryByText("Robotech")).not.toBeInTheDocument();
    expect(screen.getByText("Megabots")).toBeInTheDocument();
  });

  it("nota confirmada tem link pra corrigir", async () => {
    renderPage();
    await escolherModalidade();
    await screen.findByText("Robotech");

    expect(within(linha("Robotech")).getByRole("link", { name: /corrigir/i })).toHaveAttribute(
      "href",
      "/lancamentos/l-1/corrigir",
    );
  });

  it("nota pendente nao tem corrigir (ainda nao foi confirmada), so anular", async () => {
    renderPage();
    await escolherModalidade();
    await screen.findByText("Megabots");

    expect(within(linha("Megabots")).queryByRole("link", { name: /corrigir/i })).toBeNull();
    expect(within(linha("Megabots")).getByRole("button", { name: /anular/i })).toBeInTheDocument();
  });

  it("nota anulada aparece marcada e sem acoes", async () => {
    renderPage();
    await escolherModalidade();
    await screen.findByText("Antigos");

    const item = linha("Antigos");
    expect(within(item).getByText(/anulada/i)).toBeInTheDocument();
    expect(within(item).queryByRole("button")).toBeNull();
    expect(within(item).queryByRole("link")).toBeNull();
  });

  it("anular exige justificativa antes de enviar", async () => {
    renderPage();
    await escolherModalidade();
    await screen.findByText("Robotech");

    await userEvent.click(within(linha("Robotech")).getByRole("button", { name: /anular/i }));

    const confirmar = screen.getByRole("button", { name: /sim, anular/i });
    expect(confirmar).toBeDisabled();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("anular com justificativa chama a API", async () => {
    renderPage();
    await escolherModalidade();
    await screen.findByText("Robotech");

    await userEvent.click(within(linha("Robotech")).getByRole("button", { name: /anular/i }));
    await userEvent.type(screen.getByLabelText(/por que/i), "Pontuou a equipe errada");
    await userEvent.click(screen.getByRole("button", { name: /sim, anular/i }));

    expect(api.POST).toHaveBeenCalledWith("/api/v1/lancamentos/{lancamento_id}/anular", {
      params: { path: { lancamento_id: "l-1" } },
      body: { justificativa: "Pontuou a equipe errada" },
    });
  });

  it("mostra o erro da API se a anulacao falhar", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { mensagem: "Este lancamento ja foi anulado." } },
    } as never);
    renderPage();
    await escolherModalidade();
    await screen.findByText("Robotech");

    await userEvent.click(within(linha("Robotech")).getByRole("button", { name: /anular/i }));
    await userEvent.type(screen.getByLabelText(/por que/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /sim, anular/i }));

    expect(await screen.findByText(/ja foi anulado/i)).toBeInTheDocument();
  });
});
