import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { FichaPreviewPage } from "./FichaPreviewPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const original = await importOriginal<typeof import("react-router-dom")>();
  return { ...original, useNavigate: () => navigateMock };
});

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: (error: unknown) => {
    const erro = (error as { erro?: { codigo: string; mensagem: string } })?.erro;
    return erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." };
  },
}));

function fichaCompleta() {
  return {
    id: "ficha-1",
    modalidade_id: "mod-1",
    nivel: 1,
    versao: 1,
    status: "PUBLICADA",
    grupos: [
      {
        id: "grupo-1",
        ficha_id: "ficha-1",
        nome: "Parte Tecnica",
        ordem: 1,
        criterios: [
          {
            id: "crit-contador",
            grupo_id: "grupo-1",
            nome: "Lombada",
            categoria: "PONTUACAO",
            tipo: "CONTADOR",
            pontos: 10,
            valores_permitidos: null,
            max_ocorrencias: 2,
            modificador_tipo: null,
            modificador_valor: null,
            ordem: 1,
            ativo: true,
          },
          {
            id: "crit-escala",
            grupo_id: "grupo-1",
            nome: "Nota Artistica",
            categoria: "PONTUACAO",
            tipo: "ESCALA",
            pontos: null,
            valores_permitidos: [0, 5, 10],
            max_ocorrencias: null,
            modificador_tipo: null,
            modificador_valor: null,
            ordem: 2,
            ativo: true,
          },
          {
            id: "crit-modificador",
            grupo_id: "grupo-1",
            nome: "Excedeu tempo",
            categoria: "PENALIDADE",
            tipo: "MODIFICADOR",
            pontos: null,
            valores_permitidos: null,
            max_ocorrencias: null,
            modificador_tipo: "PERCENTUAL",
            modificador_valor: 10,
            ordem: 3,
            ativo: true,
          },
          {
            id: "crit-booleano",
            grupo_id: "grupo-1",
            nome: "Finalizacao com sucesso",
            categoria: "PONTUACAO",
            tipo: "BOOLEANO",
            pontos: 50,
            valores_permitidos: null,
            max_ocorrencias: null,
            modificador_tipo: null,
            modificador_valor: null,
            ordem: 4,
            ativo: true,
          },
          {
            id: "crit-colisao",
            grupo_id: "grupo-1",
            nome: "Colisao",
            categoria: "PENALIDADE",
            tipo: "CONTADOR",
            pontos: 20,
            valores_permitidos: null,
            max_ocorrencias: null,
            modificador_tipo: null,
            modificador_valor: null,
            ordem: 5,
            ativo: true,
          },
          {
            id: "crit-escala-penalidade",
            grupo_id: "grupo-1",
            nome: "Erro de percurso",
            categoria: "PENALIDADE",
            tipo: "ESCALA",
            pontos: null,
            valores_permitidos: [0, 5, 10],
            max_ocorrencias: null,
            modificador_tipo: null,
            modificador_valor: null,
            ordem: 6,
            ativo: true,
          },
        ],
      },
    ],
  };
}

function mockGet(
  fichaOverride: ReturnType<typeof fichaCompleta> = fichaCompleta(),
  fichasDaModalidade: Array<{ id: string; nivel: number | null; versao: number; status: string }> = [
    { id: "ficha-1", nivel: 1, versao: 1, status: "PUBLICADA" },
  ],
) {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/fichas/{ficha_id}") {
      return { data: fichaOverride, error: undefined } as never;
    }
    return {
      data: {
        itens: fichasDaModalidade,
        total: fichasDaModalidade.length,
        page: 1,
        size: 50,
      },
      error: undefined,
    } as never;
  });
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/fichas/ficha-1/preview"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/fichas/:fichaId/preview"
            element={<FichaPreviewPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FichaPreviewPage", () => {
  it("mostra os criterios da ficha e o total parcial", async () => {
    mockGet();

    renderPage();

    expect(await screen.findByText("Lombada")).toBeInTheDocument();
    expect(screen.getByText("Nota Artistica")).toBeInTheDocument();
    expect(screen.getByText("Excedeu tempo")).toBeInTheDocument();
    expect(screen.getByText(/total parcial/i)).toBeInTheDocument();
  });

  it("mostra um link para voltar ao editor da ficha", async () => {
    mockGet();

    renderPage();

    const link = await screen.findByRole("link", { name: /voltar/i });
    expect(link).toHaveAttribute(
      "href",
      "/eventos/evt-1/modalidades/mod-1/fichas/ficha-1/editar",
    );
  });

  it("mostra um seletor de fichas da modalidade e navega ao trocar", async () => {
    mockGet(fichaCompleta(), [
      { id: "ficha-1", nivel: 1, versao: 1, status: "PUBLICADA" },
      { id: "ficha-2", nivel: 2, versao: 1, status: "RASCUNHO" },
    ]);

    renderPage();

    const seletor = await screen.findByLabelText(/selecionar ficha/i);
    await userEvent.selectOptions(seletor, "ficha-2");

    expect(navigateMock).toHaveBeenCalledWith(
      "/eventos/evt-1/modalidades/mod-1/fichas/ficha-2/preview",
    );
  });

  it("criterio booleano mostra um toggle (nao +/-) e envia no maximo ocorrencias 1", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        total: 50,
        subtotais_por_grupo: {},
        detalhamento_por_criterio: [],
        modificadores_aplicados: [],
      },
      error: undefined,
    } as never);

    renderPage();

    expect(
      screen.queryByRole("button", { name: /aumentar finalizacao com sucesso/i }),
    ).not.toBeInTheDocument();

    const toggle = await screen.findByLabelText(/finalizacao com sucesso/i);
    await userEvent.click(toggle);

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/fichas/{ficha_id}/simular",
        expect.objectContaining({
          body: { valores: [{ criterio_id: "crit-booleano", ocorrencias: 1 }] },
        }),
      ),
    );

    await userEvent.click(toggle);

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/fichas/{ficha_id}/simular",
        expect.objectContaining({
          body: { valores: [{ criterio_id: "crit-booleano", ocorrencias: 0 }] },
        }),
      ),
    );
  });

  it("incrementa um contador e atualiza o total parcial com a resposta do /simular", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        total: 10,
        subtotais_por_grupo: {},
        detalhamento_por_criterio: [],
        modificadores_aplicados: [],
      },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /aumentar lombada/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/fichas/{ficha_id}/simular",
        expect.objectContaining({
          body: { valores: [{ criterio_id: "crit-contador", ocorrencias: 1 }] },
        }),
      ),
    );
    expect(await screen.findByTestId("total-parcial")).toHaveTextContent("10");
  });

  it("nao deixa incrementar acima do max_ocorrencias", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        total: 20,
        subtotais_por_grupo: {},
        detalhamento_por_criterio: [],
        modificadores_aplicados: [],
      },
      error: undefined,
    } as never);

    renderPage();

    const botaoAumentar = await screen.findByRole("button", { name: /aumentar lombada/i });
    await userEvent.click(botaoAumentar);
    await userEvent.click(botaoAumentar);
    await userEvent.click(botaoAumentar);

    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(2));
  });

  it("seleciona um valor de escala e envia para o /simular", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        total: 5,
        subtotais_por_grupo: {},
        detalhamento_por_criterio: [],
        modificadores_aplicados: [],
      },
      error: undefined,
    } as never);

    renderPage();

    const containerEscala = await screen.findByTestId("criterio-crit-escala");
    await userEvent.click(within(containerEscala).getByRole("button", { name: "5" }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/fichas/{ficha_id}/simular",
        expect.objectContaining({
          body: { valores: [{ criterio_id: "crit-escala", valor: 5 }] },
        }),
      ),
    );
  });

  it("alterna o modificador e envia aplicado para o /simular", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        total: 0,
        subtotais_por_grupo: {},
        detalhamento_por_criterio: [],
        modificadores_aplicados: [],
      },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByLabelText(/excedeu tempo/i));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/fichas/{ficha_id}/simular",
        expect.objectContaining({
          body: { valores: [{ criterio_id: "crit-modificador", aplicado: true }] },
        }),
      ),
    );
  });

  it("mostra a mensagem de erro quando o /simular falha", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: {
        erro: { codigo: "CRITERIO_MAX_OCORRENCIAS_EXCEDIDO", mensagem: "Limite excedido." },
      },
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /aumentar lombada/i }));

    expect(await screen.findByText(/limite excedido/i)).toBeInTheDocument();
  });

  it("criterio contador de penalidade fica com estilo vermelho quando incrementado", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        total: -20,
        subtotais_por_grupo: {},
        detalhamento_por_criterio: [],
        modificadores_aplicados: [],
      },
      error: undefined,
    } as never);

    renderPage();

    const container = await screen.findByTestId("criterio-crit-colisao");
    expect(container).not.toHaveClass("border-red-300");

    await userEvent.click(screen.getByRole("button", { name: /aumentar colisao/i }));

    await waitFor(() => expect(container).toHaveClass("border-red-300"));
  });

  it("criterio de escala de penalidade fica vermelho quando o valor selecionado", async () => {
    mockGet();
    vi.mocked(api.POST).mockResolvedValue({
      data: {
        total: -5,
        subtotais_por_grupo: {},
        detalhamento_por_criterio: [],
        modificadores_aplicados: [],
      },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByText("Erro de percurso");
    const botoesCinco = screen.getAllByRole("button", { name: "5" });
    const botaoPontuacao = botoesCinco.find((b) =>
      b.closest("[data-testid='criterio-crit-escala']"),
    );
    const botaoPenalidade = botoesCinco.find((b) =>
      b.closest("[data-testid='criterio-crit-escala-penalidade']"),
    );
    expect(botaoPontuacao).toBeDefined();
    expect(botaoPenalidade).toBeDefined();

    await userEvent.click(botaoPenalidade!);

    expect(botaoPenalidade).toHaveClass("bg-red-600");
    // o botao "5" da escala de pontuacao (crit-escala) nao deve ser afetado
    expect(botaoPontuacao).not.toHaveClass("bg-red-600");
  });
});
