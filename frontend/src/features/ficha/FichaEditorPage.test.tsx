import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { FichaEditorPage } from "./FichaEditorPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const original = await importOriginal<typeof import("react-router-dom")>();
  return { ...original, useNavigate: () => navigateMock };
});

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function fichaRascunho() {
  return {
    id: "ficha-1",
    modalidade_id: "mod-1",
    nivel: 1,
    versao: 1,
    status: "RASCUNHO",
    publicada_em: null,
    grupos: [
      {
        id: "grupo-1",
        ficha_id: "ficha-1",
        nome: "Parte Tecnica",
        ordem: 1,
        criterios: [
          {
            id: "crit-1",
            grupo_id: "grupo-1",
            nome: "Lombada",
            descricao: null,
            categoria: "PONTUACAO",
            tipo: "CONTADOR",
            pontos: 10,
            valores_permitidos: null,
            max_ocorrencias: null,
            modificador_tipo: null,
            modificador_valor: null,
            ordem: 1,
            ativo: true,
          },
        ],
      },
    ],
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/fichas/ficha-1/editar"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/fichas/:fichaId/editar"
            element={<FichaEditorPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FichaEditorPage", () => {
  it("mostra o badge de versao e status, e o grupo/criterio existentes", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: fichaRascunho(), error: undefined } as never);

    renderPage();

    expect(await screen.findByText(/v1/i)).toBeInTheDocument();
    expect(screen.getByText(/rascunho/i)).toBeInTheDocument();
    expect(screen.getByText("Parte Tecnica")).toBeInTheDocument();
    expect(screen.getByText("Lombada")).toBeInTheDocument();
  });

  it("mostra se o criterio e pontuacao ou penalidade na listagem", async () => {
    const ficha = fichaRascunho();
    ficha.grupos[0].criterios.push({
      id: "crit-2",
      grupo_id: "grupo-1",
      nome: "Colisao",
      descricao: null,
      categoria: "PENALIDADE",
      tipo: "CONTADOR",
      pontos: 20,
      valores_permitidos: null,
      max_ocorrencias: null,
      modificador_tipo: null,
      modificador_valor: null,
      ordem: 2,
      ativo: true,
    });
    vi.mocked(api.GET).mockResolvedValue({ data: ficha, error: undefined } as never);

    renderPage();

    const linhaLombada = (await screen.findByText("Lombada")).closest("li")!;
    expect(within(linhaLombada).getByText(/pontuacao/i)).toBeInTheDocument();

    const linhaColisao = screen.getByText("Colisao").closest("li")!;
    expect(within(linhaColisao).getByText(/penalidade/i)).toBeInTheDocument();
  });

  it("mostra aviso de que publicar congela a ficha, e o botao so aparece em rascunho", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: fichaRascunho(), error: undefined } as never);

    renderPage();

    expect(await screen.findByRole("button", { name: /publicar/i })).toBeInTheDocument();
    expect(screen.getByText(/publicar/i, { selector: "button, p" })).toBeInTheDocument();
  });

  it("nao mostra o botao de publicar quando a ficha ja esta publicada", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { ...fichaRascunho(), status: "PUBLICADA", versao: 2 },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByText(/v2/i);
    expect(screen.queryByRole("button", { name: /publicar/i })).not.toBeInTheDocument();
    expect(screen.getByText(/qualquer edi[cç][aã]o cria uma nova vers[aã]o/i)).toBeInTheDocument();
    expect(screen.getByText(/notas j[aá] lan[cç]adas n[aã]o mudam/i)).toBeInTheDocument();
  });

  it("adiciona um novo grupo", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: fichaRascunho(), error: undefined } as never);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "grupo-2", ficha_id: "ficha-1", nome: "Penalidades", ordem: 2 },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.type(await screen.findByLabelText(/nome do grupo/i), "Penalidades");
    await userEvent.click(screen.getByRole("button", { name: /adicionar grupo/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/fichas/{ficha_id}/grupos",
        expect.objectContaining({ body: { nome: "Penalidades", ordem: 2 } }),
      ),
    );
  });

  it("adiciona um criterio contador ao grupo", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/fichas/{ficha_id}") {
        return { data: fichaRascunho(), error: undefined } as never;
      }
      return {
        data: {
          itens: [{ id: "ficha-1", nivel: 1, versao: 1, status: "RASCUNHO" }],
          total: 1,
          page: 1,
          size: 10,
        },
        error: undefined,
      } as never;
    });
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "crit-2", grupo_id: "grupo-1" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /adicionar criterio/i }));
    await userEvent.type(screen.getByLabelText(/nome do criterio/i), "Finalizacao");
    await userEvent.type(screen.getByLabelText(/^pontos$/i), "50");
    await userEvent.click(screen.getByRole("button", { name: /salvar criterio/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/grupos/{grupo_id}/criterios",
        expect.objectContaining({
          body: expect.objectContaining({
            nome: "Finalizacao",
            categoria: "PONTUACAO",
            tipo: "CONTADOR",
            pontos: 50,
          }),
        }),
      ),
    );
  });

  it("mostra valores permitidos em vez de pontos quando o formato e escala", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: fichaRascunho(), error: undefined } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /adicionar criterio/i }));
    expect(screen.getByLabelText(/^pontos$/i)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/formato do criterio/i), "ESCALA");

    expect(screen.queryByLabelText(/^pontos$/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/valores permitidos/i)).toBeInTheDocument();
  });

  it("cria um criterio de penalidade escolhendo 'Tipo de criterio' = Penalidade", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: fichaRascunho(), error: undefined } as never);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "crit-3", grupo_id: "grupo-1" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /adicionar criterio/i }));
    await userEvent.type(screen.getByLabelText(/nome do criterio/i), "Colisao");
    await userEvent.selectOptions(screen.getByLabelText(/tipo de criterio/i), "PENALIDADE");
    await userEvent.type(screen.getByLabelText(/^pontos$/i), "20");
    await userEvent.click(screen.getByRole("button", { name: /salvar criterio/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/grupos/{grupo_id}/criterios",
        expect.objectContaining({
          body: expect.objectContaining({
            nome: "Colisao",
            categoria: "PENALIDADE",
            tipo: "CONTADOR",
            pontos: 20,
          }),
        }),
      ),
    );
  });

  it("so mostra 'zera total' no modificador quando o tipo de criterio e penalidade", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: fichaRascunho(), error: undefined } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /adicionar criterio/i }));
    await userEvent.selectOptions(screen.getByLabelText(/formato do criterio/i), "MODIFICADOR");

    const opcoesPontuacao = screen.getByLabelText(/tipo de modificador/i);
    expect(within(opcoesPontuacao).queryByText(/zera total/i)).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/^tipo de criterio$/i), "PENALIDADE");

    expect(
      within(screen.getByLabelText(/tipo de modificador/i)).getByText(/zera total/i),
    ).toBeInTheDocument();
  });

  it("publica a ficha", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: fichaRascunho(), error: undefined } as never);
    vi.mocked(api.POST).mockResolvedValue({
      data: { ...fichaRascunho(), status: "PUBLICADA" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /publicar/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/fichas/{ficha_id}/publicar",
        expect.objectContaining({ params: { path: { ficha_id: "ficha-1" } } }),
      ),
    );
  });

  it("ao editar um criterio de ficha publicada e o backend retorna nova ficha, navega para a nova versao", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/fichas/{ficha_id}") {
        return {
          data: { ...fichaRascunho(), status: "PUBLICADA" },
          error: undefined,
        } as never;
      }
      // busca de sincronizacao apos a edicao: aponta pra nova ficha ativa
      return {
        data: {
          itens: [{ id: "ficha-2", nivel: 1, versao: 2, status: "PUBLICADA" }],
          total: 1,
          page: 1,
          size: 10,
        },
        error: undefined,
      } as never;
    });
    vi.mocked(api.PATCH).mockResolvedValue({
      data: { id: "crit-99", grupo_id: "grupo-99" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /editar criterio/i }));
    const pontos = screen.getByLabelText(/^pontos$/i);
    await userEvent.clear(pontos);
    await userEvent.type(pontos, "20");
    await userEvent.click(screen.getByRole("button", { name: /salvar criterio/i }));

    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith(
        "/eventos/evt-1/modalidades/mod-1/fichas/ficha-2/editar",
        { replace: true },
      ),
    );
  });
});
