import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { EquipeListPage } from "./EquipeListPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <EquipeListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function logarComo(papel: string) {
  useAuthStore.setState({
    accessToken: "tok",
    refreshToken: "tok",
    usuario: { id: "u1", nome: "Usuario Teste", email: "user@tjr.app", papel },
  });
}

// Mocka o GET generico do client (usado tanto pra /equipes quanto pra
// /modalidades, que alimenta o filtro) roteando pelo path -- sem isso os dois
// hooks de useQuery da pagina recebiam o mesmo payload de equipes, duplicando
// nomes na tela (equipe vira tambem opcao do <select> de modalidade) e
// quebrando os testes que buscam por texto unico.
function mockGetEquipes(
  equipesPayload: unknown,
  modalidadesPayload: unknown = { itens: [], total: 0, page: 1, size: 200 },
  inscricoesPayload: unknown = { itens: [], total: 0, page: 1, size: 1000 },
) {
  vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
    if (path === "/api/v1/modalidades") {
      return { data: modalidadesPayload, error: undefined } as never;
    }
    if (path === "/api/v1/equipes") {
      return { data: equipesPayload, error: undefined } as never;
    }
    if (path === "/api/v1/inscricoes") {
      return { data: inscricoesPayload, error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  logarComo("COORDENADOR");
});

describe("EquipeListPage", () => {
  it("lista as equipes cadastradas com nivel e status", async () => {
    mockGetEquipes({
      itens: [
        { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true },
        { id: "eq2", nome: "Equipe Beta", nivel: 3, ativo: false },
      ],
      total: 2,
      page: 1,
      size: 50,
    });

    renderPage();

    const linhaAlpha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const linhaBeta = screen.getByText("Equipe Beta").closest("li")!;

    expect(within(linhaAlpha).getByText(/nível 2/i)).toBeInTheDocument();
    expect(within(linhaBeta).getByText(/inativa/i)).toBeInTheDocument();
  });

  it("mostra as modalidades em que cada equipe esta inscrita", async () => {
    mockGetEquipes(
      {
        itens: [
          { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true },
          { id: "eq2", nome: "Equipe Beta", nivel: 3, ativo: true },
        ],
        total: 2,
        page: 1,
        size: 50,
      },
      {
        itens: [
          { id: "mod-1", nome: "Sumô" },
          { id: "mod-2", nome: "Cabo de Guerra" },
        ],
        total: 2,
        page: 1,
        size: 200,
      },
      {
        itens: [
          { id: "ins-1", equipe_id: "eq1", modalidade_id: "mod-1" },
          { id: "ins-2", equipe_id: "eq1", modalidade_id: "mod-2" },
        ],
        total: 2,
        page: 1,
        size: 1000,
      },
    );

    renderPage();

    const linhaAlpha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const linhaBeta = screen.getByText("Equipe Beta").closest("li")!;

    expect(within(linhaAlpha).getByText(/Sumô, Cabo de Guerra/)).toBeInTheDocument();
    expect(within(linhaBeta).getByText(/nenhuma modalidade/i)).toBeInTheDocument();
  });

  it("filtra equipes por modalidade", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: unknown, options?: unknown) => {
      if (path === "/api/v1/modalidades") {
        return {
          data: {
            itens: [
              { id: "mod-1", nome: "Sumo" },
              { id: "mod-2", nome: "Danca" },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        const query = (options as { params?: { query?: Record<string, unknown> } })?.params
          ?.query;
        if (query?.modalidade_id === "mod-1") {
          return {
            data: {
              itens: [{ id: "eq1", nome: "Equipe Sumo", nivel: 1, ativo: true }],
              total: 1,
              page: 1,
              size: 100,
            },
            error: undefined,
          } as never;
        }
        return {
          data: {
            itens: [
              { id: "eq1", nome: "Equipe Sumo", nivel: 1, ativo: true },
              { id: "eq2", nome: "Equipe Danca", nivel: 1, ativo: true },
            ],
            total: 2,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await screen.findByText("Equipe Sumo");
    expect(screen.getByText("Equipe Danca")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/filtrar por modalidade/i), "mod-1");

    await waitFor(() => expect(screen.queryByText("Equipe Danca")).not.toBeInTheDocument());
    expect(screen.getByText("Equipe Sumo")).toBeInTheDocument();
  });

  it("busca equipes pelo nome digitado, sem diferenciar maiusculas", async () => {
    mockGetEquipes({
      itens: [
        { id: "eq1", nome: "ABCMP", nivel: 2, ativo: true },
        { id: "eq2", nome: "Robocop Rosa", nivel: 2, ativo: true },
        { id: "eq3", nome: "Hefesto Tech", nivel: 3, ativo: true },
      ],
      total: 3,
      page: 1,
      size: 50,
    });

    renderPage();

    await screen.findByText("ABCMP");
    expect(screen.getByText("Robocop Rosa")).toBeInTheDocument();
    expect(screen.getByText("Hefesto Tech")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/buscar equipe/i), "hefesto");

    await waitFor(() => expect(screen.queryByText("ABCMP")).not.toBeInTheDocument());
    expect(screen.queryByText("Robocop Rosa")).not.toBeInTheDocument();
    expect(screen.getByText("Hefesto Tech")).toBeInTheDocument();
  });

  it("linka para a tela de submissoes da equipe", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

    renderPage();

    const linha = (await screen.findByText("Equipe Alpha")).closest("li")!;
    const link = within(linha).getByRole("link", { name: /submiss(o|õ)es/i });
    expect(link).toHaveAttribute("href", "/equipes/eq1/submissoes");
  });

  it("cria uma equipe pelo formulario", async () => {
    mockGetEquipes({ itens: [], total: 0, page: 1, size: 50 });
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "nova-equipe", nome: "Equipe Nova", nivel: 1, ativo: true },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "Equipe Nova");
    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "1");
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/equipes",
        expect.objectContaining({ body: { nome: "Equipe Nova", nivel: 1, ativo: true } }),
      ),
    );
  });

  it("formulario de criar equipe mostra so as modalidades compativeis com o nivel selecionado", async () => {
    mockGetEquipes(
      { itens: [], total: 0, page: 1, size: 50 },
      {
        itens: [
          { id: "mod-1", nome: "Sumô", niveis_aplicaveis: [2, 3, 4] },
          { id: "mod-2", nome: "Sumô RC 1,5 kg", niveis_aplicaveis: [1] },
        ],
        total: 2,
        page: 1,
        size: 200,
      },
    );

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    const secaoModalidades = screen.getByRole("group", { name: /modalidades/i });
    await within(secaoModalidades).findByLabelText("Sumô RC 1,5 kg");
    expect(within(secaoModalidades).queryByLabelText("Sumô")).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "2");

    expect(within(secaoModalidades).getByLabelText("Sumô")).toBeInTheDocument();
    expect(within(secaoModalidades).queryByLabelText("Sumô RC 1,5 kg")).not.toBeInTheDocument();
  });

  it("cria equipe e ja inscreve nas modalidades marcadas no formulario", async () => {
    mockGetEquipes(
      { itens: [], total: 0, page: 1, size: 50 },
      {
        itens: [
          { id: "mod-1", nome: "Cabo de Guerra", niveis_aplicaveis: [1] },
          { id: "mod-2", nome: "Corrida de Carros Autônomos", niveis_aplicaveis: [1] },
        ],
        total: 2,
        page: 1,
        size: 200,
      },
    );
    vi.mocked(api.POST).mockImplementation(async (path: unknown, opts?: unknown) => {
      if (path === "/api/v1/equipes") {
        return {
          data: { id: "nova-equipe", nome: "Equipe Nova", nivel: 1, ativo: true },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return { data: { id: "ins-x", ...(opts as { body: object }).body }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "Equipe Nova");
    await userEvent.click(await screen.findByLabelText("Cabo de Guerra"));
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/inscricoes",
        expect.objectContaining({ body: { equipe_id: "nova-equipe", modalidade_id: "mod-1" } }),
      ),
    );
    expect(api.POST).not.toHaveBeenCalledWith(
      "/api/v1/inscricoes",
      expect.objectContaining({ body: expect.objectContaining({ modalidade_id: "mod-2" }) }),
    );
  });

  it("BUG-07: nao envia o formulario quando o nome tem so espacos", async () => {
    mockGetEquipes({ itens: [], total: 0, page: 1, size: 50 });

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "   ");
    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "1");
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    expect(await screen.findByText(/informe o nome da equipe/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("BUG-07: tira espaco das pontas do nome antes de enviar", async () => {
    mockGetEquipes({ itens: [], total: 0, page: 1, size: 50 });
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "nova-equipe", nome: "Equipe Nova", nivel: 1, ativo: true },
      error: undefined,
    } as never);

    renderPage();

    await screen.findByRole("button", { name: /criar equipe/i });
    await userEvent.type(screen.getByLabelText(/nome da equipe/i), "  Equipe Nova  ");
    await userEvent.selectOptions(screen.getByLabelText(/nivel da equipe/i), "1");
    await userEvent.click(screen.getByRole("button", { name: /criar equipe/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/equipes",
        expect.objectContaining({ body: { nome: "Equipe Nova", nivel: 1, ativo: true } }),
      ),
    );
  });

  it("desativa uma equipe ativa", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });
    vi.mocked(api.PATCH).mockResolvedValue({
      data: { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: false },
      error: undefined,
    } as never);

    renderPage();

    const botao = await screen.findByRole("button", { name: /desativar/i });
    await userEvent.click(botao);

    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith(
        "/api/v1/equipes/{equipe_id}",
        expect.objectContaining({
          params: { path: { equipe_id: "eq1" } },
          body: { ativo: false },
        }),
      ),
    );
  });

  // Bug real de campo (dia do TJR 2026): com a rede do ginasio, o PATCH demora
  // 1-3s e a tela nao dava sinal nenhum de que algo estava acontecendo -- o
  // coordenador clicava de novo, e o audit_log de producao registrou o mesmo
  // `{ativo: false}` varias vezes seguidas pra mesma equipe.
  it("nao dispara um segundo PATCH enquanto o primeiro ainda esta em voo", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });
    let resolverPatch: (valor: unknown) => void = () => {};
    vi.mocked(api.PATCH).mockReturnValue(
      new Promise((resolve) => {
        resolverPatch = resolve;
      }) as never,
    );

    renderPage();

    const botao = await screen.findByRole("button", { name: /desativar/i });
    await userEvent.click(botao);

    const emAndamento = await screen.findByRole("button", { name: /desativando/i });
    expect(emAndamento).toBeDisabled();

    await userEvent.click(emAndamento);
    await userEvent.click(emAndamento);

    resolverPatch({
      data: { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: false },
      error: undefined,
    });

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
  });

  // Verificado ao vivo contra producao: o `disabled` sozinho nao basta. Cliques
  // no mesmo tick (fila da rede do ginasio liberando de uma vez -- o audit_log
  // tem 3 PATCH em 4ms) acontecem antes do React re-renderizar, entao a guarda
  // por estado ainda deixa todos passarem. Tem que ser trava sincrona.
  it("ignora cliques repetidos disparados no mesmo instante", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });
    vi.mocked(api.PATCH).mockReturnValue(new Promise(() => {}) as never);

    renderPage();

    const botao = await screen.findByRole("button", { name: /desativar/i });
    // Clique nativo em sequencia, dentro do mesmo tick e sem flush do React
    // entre eles -- e o que o navegador faz de verdade (`fireEvent` re-renderiza
    // a cada chamada, o que esconderia justamente o caso que quebrou em campo).
    await act(async () => {
      botao.click();
      botao.click();
      botao.click();
    });

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
  });

  it("mostra a equipe como inativa assim que o PATCH responde, sem esperar o refetch da lista", async () => {
    // O primeiro GET responde normal (monta a tela); o refetch disparado depois
    // do PATCH fica pendurado de proposito, simulando a lista das 136 equipes
    // reais demorando na rede do ginasio. O selo tem que mudar com a resposta do
    // proprio PATCH, sem depender desse refetch.
    //
    // (Nao se testa aqui "o valor do PATCH sobrevive a um refetch que traz outro
    // valor": o servidor e a fonte da verdade, entao dado fresco da listagem tem
    // que vencer mesmo. O que o bug de campo exigia era so nao esperar por ele.)
    const equipeAtiva = { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true };
    let chamadasEquipes = 0;
    vi.mocked(api.GET).mockImplementation(async (path: unknown) => {
      if (path === "/api/v1/equipes") {
        chamadasEquipes += 1;
        if (chamadasEquipes > 1) return new Promise(() => {}) as never;
        return { data: { itens: [equipeAtiva], total: 1, page: 1, size: 50 }, error: undefined } as never;
      }
      return { data: { itens: [], total: 0, page: 1, size: 50 }, error: undefined } as never;
    });
    vi.mocked(api.PATCH).mockResolvedValue({
      data: { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: false },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /desativar/i }));

    expect(await screen.findByText(/inativa/i)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /^ativar$/i })).toBeInTheDocument();
  });

  it("mostra erro na tela quando o PATCH de desativar falha", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });
    vi.mocked(api.PATCH).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "QUALQUER", mensagem: "falhou" } },
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /desativar/i }));

    expect(await screen.findByText(/não foi possível/i)).toBeInTheDocument();
    // sem mudanca otimista: a equipe continua ativa, porque o servidor recusou
    expect(screen.getByText(/^Ativa$/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /desativar/i })).toBeEnabled();
  });

  // Mesmo defeito do botao de desativar, na mesma tela: o audit_log de producao
  // do dia do evento tem 5 PATCH de renomear a mesma equipe em 400ms.
  it("nao dispara um segundo PATCH de salvar enquanto o primeiro ainda esta em voo", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });
    let resolverPatch: (valor: unknown) => void = () => {};
    vi.mocked(api.PATCH).mockReturnValue(
      new Promise((resolve) => {
        resolverPatch = resolve;
      }) as never,
    );

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /editar/i }));
    await userEvent.click(screen.getByRole("button", { name: /salvar/i }));

    const emAndamento = await screen.findByRole("button", { name: /salvando/i });
    expect(emAndamento).toBeDisabled();

    await userEvent.click(emAndamento);
    await userEvent.click(emAndamento);

    resolverPatch({
      data: { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true },
      error: undefined,
    });

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
  });

  it("coordenador marca uma equipe presente como ausente", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true, presente: true }],
      total: 1,
      page: 1,
      size: 50,
    });
    vi.mocked(api.PATCH).mockResolvedValue({
      data: { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true, presente: false },
      error: undefined,
    } as never);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /marcar ausente/i }));

    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith(
        "/api/v1/equipes/{equipe_id}",
        expect.objectContaining({
          params: { path: { equipe_id: "eq1" } },
          body: { presente: false },
        }),
      ),
    );
  });

  it("equipe ausente mostra o selo 'Ausente' e permite marcar presente de novo", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true, presente: false }],
      total: 1,
      page: 1,
      size: 50,
    });
    vi.mocked(api.PATCH).mockResolvedValue({
      data: { id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true, presente: true },
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByText("Ausente")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /marcar presente/i }));
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith(
        "/api/v1/equipes/{equipe_id}",
        expect.objectContaining({ body: { presente: true } }),
      ),
    );
  });

  it("marcar ausente tambem ignora cliques repetidos no mesmo instante", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true, presente: true }],
      total: 1,
      page: 1,
      size: 50,
    });
    vi.mocked(api.PATCH).mockReturnValue(new Promise(() => {}) as never);

    renderPage();

    const botao = await screen.findByRole("button", { name: /marcar ausente/i });
    await act(async () => {
      botao.click();
      botao.click();
      botao.click();
    });

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
  });

  it("arbitro nao ve o formulario de criar equipe nem os botoes de editar/ativar", async () => {
    logarComo("ARBITRO");
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.queryByRole("button", { name: /^criar equipe$/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/nome da equipe/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /desativar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /marcar ausente/i })).not.toBeInTheDocument();
    // leitura continua liberada
    expect(screen.getByRole("link", { name: /submiss/i })).toBeInTheDocument();
  });

  it("secretaria tambem nao ve criar/editar/ativar, so leitura", async () => {
    logarComo("SECRETARIA");
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.queryByRole("button", { name: /^criar equipe$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /desativar/i })).not.toBeInTheDocument();
  });

  it("coordenador continua vendo criar/editar/ativar", async () => {
    mockGetEquipes({
      itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }],
      total: 1,
      page: 1,
      size: 50,
    });

    renderPage();

    await screen.findByText("Equipe Alpha");
    expect(screen.getByRole("button", { name: /^criar equipe$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^editar$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /desativar/i })).toBeInTheDocument();
  });

  it("coordenador abre o painel de modalidades e ve as inscritas com opcao de remover", async () => {
    mockGetEquipes(
      { itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }], total: 1, page: 1, size: 50 },
      {
        itens: [
          { id: "mod-1", nome: "Sumô", niveis_aplicaveis: [2, 3, 4] },
          { id: "mod-2", nome: "Cabo de Guerra", niveis_aplicaveis: [2, 3, 4] },
        ],
        total: 2,
        page: 1,
        size: 200,
      },
      {
        itens: [{ id: "ins-1", equipe_id: "eq1", modalidade_id: "mod-1" }],
        total: 1,
        page: 1,
        size: 1000,
      },
    );

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /^editar$/i }));

    const painel = (await screen.findByLabelText(/modalidades de equipe alpha/i)).closest("div")!;
    expect(within(painel).getByText("Sumô")).toBeInTheDocument();
    expect(within(painel).getByRole("button", { name: /remover/i })).toBeInTheDocument();
  });

  it("select de adicionar modalidade so mostra as compativeis com o nivel da equipe, ainda nao inscritas", async () => {
    mockGetEquipes(
      { itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }], total: 1, page: 1, size: 50 },
      {
        itens: [
          { id: "mod-1", nome: "Sumô", niveis_aplicaveis: [2, 3, 4] },
          { id: "mod-2", nome: "Cabo de Guerra", niveis_aplicaveis: [2, 3, 4] },
          { id: "mod-3", nome: "Sumô RC 1,5 kg", niveis_aplicaveis: [1] },
        ],
        total: 3,
        page: 1,
        size: 200,
      },
      {
        itens: [{ id: "ins-1", equipe_id: "eq1", modalidade_id: "mod-1" }],
        total: 1,
        page: 1,
        size: 1000,
      },
    );

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /^editar$/i }));
    const seletor = await screen.findByLabelText(/adicionar modalidade/i);

    expect(within(seletor).queryByText("Sumô")).not.toBeInTheDocument();
    expect(within(seletor).getByText("Cabo de Guerra")).toBeInTheDocument();
    expect(within(seletor).queryByText("Sumô RC 1,5 kg")).not.toBeInTheDocument();
  });

  it("coordenador adiciona uma modalidade elegivel a uma equipe existente", async () => {
    mockGetEquipes(
      { itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }], total: 1, page: 1, size: 50 },
      {
        itens: [{ id: "mod-2", nome: "Cabo de Guerra", niveis_aplicaveis: [2, 3, 4] }],
        total: 1,
        page: 1,
        size: 200,
      },
      { itens: [], total: 0, page: 1, size: 1000 },
    );
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "ins-nova", equipe_id: "eq1", modalidade_id: "mod-2" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /^editar$/i }));
    await userEvent.selectOptions(await screen.findByLabelText(/adicionar modalidade/i), "mod-2");
    await userEvent.click(screen.getByRole("button", { name: /^adicionar$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/inscricoes",
        expect.objectContaining({ body: { equipe_id: "eq1", modalidade_id: "mod-2" } }),
      ),
    );
  });

  it("coordenador remove uma modalidade de uma equipe", async () => {
    mockGetEquipes(
      { itens: [{ id: "eq1", nome: "Equipe Alpha", nivel: 2, ativo: true }], total: 1, page: 1, size: 50 },
      {
        itens: [{ id: "mod-1", nome: "Sumô", niveis_aplicaveis: [2, 3, 4] }],
        total: 1,
        page: 1,
        size: 200,
      },
      {
        itens: [{ id: "ins-1", equipe_id: "eq1", modalidade_id: "mod-1" }],
        total: 1,
        page: 1,
        size: 1000,
      },
    );
    vi.mocked(api.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);

    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /^editar$/i }));
    await userEvent.click(await screen.findByRole("button", { name: /remover/i }));

    await waitFor(() =>
      expect(api.DELETE).toHaveBeenCalledWith(
        "/api/v1/inscricoes/{inscricao_id}",
        expect.objectContaining({ params: { path: { inscricao_id: "ins-1" } } }),
      ),
    );
  });
});
