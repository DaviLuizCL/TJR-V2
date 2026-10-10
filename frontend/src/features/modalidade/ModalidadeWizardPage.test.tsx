import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ModalidadeWizardPage } from "./ModalidadeWizardPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const original = await importOriginal<typeof import("react-router-dom")>();
  return { ...original, useNavigate: () => navigateMock };
});

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn() },
  extrairErro: (error: unknown) => {
    const erro = (error as { erro?: { codigo: string; mensagem: string } })?.erro;
    return erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." };
  },
}));

function renderCriar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/novo"]}>
        <Routes>
          <Route path="/eventos/:eventoId/modalidades/novo" element={<ModalidadeWizardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderEditar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/editar"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/editar"
            element={<ModalidadeWizardPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ModalidadeWizardPage - criacao", () => {
  it("mostra o passo 1 (dados basicos) primeiro", () => {
    renderCriar();

    expect(screen.getByText(/passo 1 de 5/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/nome da modalidade/i)).toBeInTheDocument();
  });

  it("nao avanca de passo se o nome estiver vazio", async () => {
    renderCriar();

    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    expect(await screen.findByText(/informe o nome da modalidade/i)).toBeInTheDocument();
    expect(screen.getByText(/passo 1 de 5/i)).toBeInTheDocument();
  });

  it("so mostra formato de chaveamento quando o tipo de disputa e confronto", async () => {
    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Sumo de Robos");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    expect(screen.queryByLabelText(/formato de chaveamento/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText(/confronto/i));

    expect(screen.getByLabelText(/formato de chaveamento/i)).toBeInTheDocument();
  });

  it("completa os 5 passos e cria a modalidade com POST", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "mod-novo" },
      error: undefined,
    } as never);

    renderCriar();

    // passo 1
    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Sumo de Robos");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    // passo 2
    await userEvent.click(screen.getByLabelText(/^confronto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    // passo 3
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    // passo 4
    const qtdRodadas = screen.getByLabelText(/quantidade de rodadas/i);
    await userEvent.clear(qtdRodadas);
    await userEvent.type(qtdRodadas, "3");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    // passo 5
    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /criar modalidade/i }));

    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    const chamada = vi.mocked(api.POST).mock.calls[0] as unknown as [string, { body: unknown }];
    const opcoes = chamada[1];
    expect((opcoes as { body: Record<string, unknown> }).body).toMatchObject({
      nome: "Sumo de Robos",
      tipo_disputa: "CONFRONTO",
      niveis_aplicaveis: [1],
      qtd_rodadas: 3,
      evento_id: "evt-1",
    });
    expect(navigateMock).toHaveBeenCalledWith("/eventos/evt-1/modalidades");
  });

  it("ao marcar ficha unica entre niveis, seleciona todos os niveis automaticamente e nao bloqueia o avanco", async () => {
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "mod-novo" }, error: undefined } as never);

    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Danca");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    // passo 3: marca ficha unica sem escolher nenhum nivel manualmente
    await userEvent.click(screen.getByLabelText(/usar uma unica ficha/i));
    expect(screen.queryByLabelText(/^absoluto$/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    // passo 4: nao mexe em nada, so avanca
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /criar modalidade/i }));

    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    const chamada = vi.mocked(api.POST).mock.calls[0] as unknown as [string, { body: unknown }];
    expect((chamada[1] as { body: Record<string, unknown> }).body).toMatchObject({
      niveis_aplicaveis: [1, 2, 3, 4],
      ficha_unica_entre_niveis: true,
    });
  });

  it("mostra tentativas por rodada e pausa entre rodadas no passo de rodadas", async () => {
    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Sumo de Robos");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    expect(screen.getByLabelText(/quantidade de rodadas/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/tentativas por rodada/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/pausa entre rodadas/i)).toBeInTheDocument();
  });

  it("permite escolher 'ignorar menor nota' sem exigir quantas rodadas contam", async () => {
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "mod-novo" }, error: undefined } as never);

    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Sumo de Robos");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.selectOptions(
      screen.getByLabelText(/como consolidar as rodadas/i),
      "IGNORA_MENOR_NOTA",
    );
    expect(screen.queryByLabelText(/quantas rodadas contam/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /criar modalidade/i }));

    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    const chamada = vi.mocked(api.POST).mock.calls[0] as unknown as [string, { body: unknown }];
    expect((chamada[1] as { body: Record<string, unknown> }).body).toMatchObject({
      consolidacao: "IGNORA_MENOR_NOTA",
    });
  });

  it("envia tentativas_por_rodada e pausa_entre_rodadas_seg ao criar a modalidade", async () => {
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "mod-novo" }, error: undefined } as never);

    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Sumo de Robos");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    const tentativas = screen.getByLabelText(/tentativas por rodada/i);
    await userEvent.clear(tentativas);
    await userEvent.type(tentativas, "3");
    const pausa = screen.getByLabelText(/pausa entre rodadas/i);
    await userEvent.type(pausa, "120");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /criar modalidade/i }));

    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    const chamada = vi.mocked(api.POST).mock.calls[0] as unknown as [string, { body: unknown }];
    expect((chamada[1] as { body: Record<string, unknown> }).body).toMatchObject({
      tentativas_por_rodada: 3,
      pausa_entre_rodadas_seg: 120,
    });
  });

  it("nao mostra mais secao de arenas na modalidade individual (arena e decidida na hora)", async () => {
    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Resgate no Plano");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    expect(screen.getByLabelText(/quantidade de rodadas/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /adicionar arena/i })).not.toBeInTheDocument();
  });

  it("nao mostra a secao de arenas nem gera rodadas/arenas quando o tipo de disputa e confronto", async () => {
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "mod-novo" }, error: undefined } as never);

    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Sumo de Robos");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^confronto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    expect(screen.queryByRole("button", { name: /adicionar arena/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /criar modalidade/i }));

    await waitFor(() => expect(navigateMock).toHaveBeenCalled());
    expect(api.POST).toHaveBeenCalledTimes(1);
  });

  it("ao criar modalidade individual, gera as rodadas e nao cria arena", async () => {
    vi.mocked(api.POST).mockImplementation((async (url: string) => {
      if (url === "/api/v1/modalidades") {
        return { data: { id: "mod-novo" }, error: undefined };
      }
      if (url === "/api/v1/rodadas/gerar") {
        return { data: [], error: undefined };
      }
      throw new Error(`chamada inesperada: ${url}`);
    }) as never);

    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Resgate no Plano");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /criar modalidade/i }));

    await waitFor(() => expect(navigateMock).toHaveBeenCalled());

    const chamadas = vi.mocked(api.POST).mock.calls as unknown as [
      string,
      { body: Record<string, unknown> },
    ][];
    expect(chamadas.map(([url]) => url)).toEqual([
      "/api/v1/modalidades",
      "/api/v1/rodadas/gerar",
    ]);
    expect(chamadas[1][1].body).toMatchObject({ modalidade_id: "mod-novo" });
  });

  it("mostra erro e nao navega se a geracao de rodadas falhar apos criar a modalidade individual", async () => {
    vi.mocked(api.POST).mockImplementation((async (url: string) => {
      if (url === "/api/v1/modalidades") {
        return { data: { id: "mod-novo" }, error: undefined };
      }
      if (url === "/api/v1/rodadas/gerar") {
        return {
          data: undefined,
          error: { erro: { codigo: "ERRO_X", mensagem: "Falha ao gerar rodadas." } },
        };
      }
      throw new Error(`chamada inesperada: ${url}`);
    }) as never);

    renderCriar();

    await userEvent.type(screen.getByLabelText(/nome da modalidade/i), "Resgate no Plano");
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByLabelText(/^absoluto$/i));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /criar modalidade/i }));

    expect(await screen.findByText(/falha ao gerar rodadas/i)).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});

describe("ModalidadeWizardPage - edicao", () => {
  it("preenche os campos com os dados existentes e salva com PATCH", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: {
        id: "mod-1",
        nome: "Sumo de Robos",
        descricao: null,
        tipo_disputa: "CONFRONTO",
        formato_chaveamento: "MATA_MATA",
        niveis_aplicaveis: [1, 2],
        ficha_unica_entre_niveis: false,
        qtd_rodadas: 3,
        tentativas_por_rodada: 3,
        duracao_maxima_rodada_seg: null,
        pausa_entre_rodadas_seg: 90,
        consolidacao: "SOMA_RODADAS",
        consolidacao_n: null,
        permite_total_negativo: false,
        desempates: null,
        status: "RASCUNHO",
      },
      error: undefined,
    } as never);
    vi.mocked(api.PATCH).mockResolvedValue({ data: { id: "mod-1" }, error: undefined } as never);

    renderEditar();

    expect(await screen.findByDisplayValue("Sumo de Robos")).toBeInTheDocument();

    for (let i = 0; i < 3; i++) {
      await userEvent.click(screen.getByRole("button", { name: /avancar/i }));
    }

    await waitFor(() =>
      expect(screen.getByLabelText(/tentativas por rodada/i)).toHaveValue(3),
    );
    expect(screen.getByLabelText(/pausa entre rodadas/i)).toHaveValue(90);
    await userEvent.click(screen.getByRole("button", { name: /avancar/i }));

    await waitFor(() => expect(screen.getByText(/passo 5 de 5/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /salvar/i }));

    await waitFor(() => expect(api.PATCH).toHaveBeenCalled());
    const chamada = vi.mocked(api.PATCH).mock.calls[0] as unknown as [string, { body: unknown }];
    expect((chamada[1] as { body: Record<string, unknown> }).body).toMatchObject({
      tentativas_por_rodada: 3,
      pausa_entre_rodadas_seg: 90,
    });
    expect(navigateMock).toHaveBeenCalledWith("/eventos/evt-1/modalidades");
  });
});
