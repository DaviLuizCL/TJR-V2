import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { LancamentoCorrecaoPage } from "./LancamentoCorrecaoPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage(caminho = "/lancamentos/lanc-1/corrigir") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[caminho]}>
        <Routes>
          <Route path="/lancamentos/:lancamentoId/corrigir" element={<LancamentoCorrecaoPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const FICHA = {
  id: "ficha-1",
  grupos: [
    {
      id: "grupo-1",
      nome: "Geral",
      criterios: [
        {
          id: "crit-1",
          nome: "Lombada",
          categoria: "PONTUACAO",
          tipo: "CONTADOR",
          pontos: 10,
          valores_permitidos: null,
          max_ocorrencias: null,
          modificador_tipo: null,
          modificador_valor: null,
        },
      ],
    },
  ],
};

const LANCAMENTO_CONFIRMADO = {
  id: "lanc-1",
  ficha_id: "ficha-1",
  revision: 1,
  status: "CONFIRMADO",
  total: 20,
  itens: [
    {
      criterio_id: "crit-1",
      criterio_snapshot: { tipo: "CONTADOR" },
      ocorrencias: 2,
      valor: null,
      pontos: 20,
    },
  ],
};

function mockGet(lancamento: unknown = LANCAMENTO_CONFIRMADO) {
  vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
    if (path === "/api/v1/lancamentos/{lancamento_id}") {
      return { data: lancamento, error: undefined } as never;
    }
    if (path === "/api/v1/fichas/{ficha_id}") {
      return { data: FICHA, error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LancamentoCorrecaoPage", () => {
  it("carrega os valores atuais do lancamento nos campos", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByTestId("criterio-crit-1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("bloqueia o envio sem justificativa", async () => {
    mockGet();
    renderPage();

    await screen.findByTestId("criterio-crit-1");
    await userEvent.click(screen.getByRole("button", { name: /salvar corre/i }));

    expect(await screen.findByText(/informe uma justificativa/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalledWith(
      "/api/v1/lancamentos/{lancamento_id}/corrigir",
      expect.anything(),
    );
  });

  it("envia a correcao com justificativa, revision e itens atualizados", async () => {
    mockGet();
    vi.mocked(api.POST).mockImplementation(async (path: unknown) => {
      if (path === "/api/v1/fichas/{ficha_id}/simular") {
        return { data: { total: 30 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/corrigir") {
        return { data: { ...LANCAMENTO_CONFIRMADO, total: 30 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await screen.findByTestId("criterio-crit-1");
    await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
    await userEvent.type(
      screen.getByLabelText(/justificativa/i),
      "Equipe contestou, corrigido apos revisao do video.",
    );
    await userEvent.click(screen.getByRole("button", { name: /salvar corre/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos/{lancamento_id}/corrigir",
        expect.objectContaining({
          params: { path: { lancamento_id: "lanc-1" } },
          body: {
            justificativa: "Equipe contestou, corrigido apos revisao do video.",
            revision: 1,
            itens: [{ criterio_id: "crit-1", ocorrencias: 3 }],
          },
        }),
      ),
    );
  });

  it("nao permite corrigir lancamento que ainda nao foi confirmado", async () => {
    mockGet({ ...LANCAMENTO_CONFIRMADO, status: "PENDENTE" });

    renderPage();

    expect(await screen.findByText(/s[oó] [eé] poss[ií]vel corrigir/i)).toBeInTheDocument();
    expect(screen.queryByTestId("criterio-crit-1")).not.toBeInTheDocument();
  });
});
