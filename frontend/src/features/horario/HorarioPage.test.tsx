import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { HorarioPage } from "./HorarioPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn() },
  extrairErro: (error: unknown) => {
    const erro = (error as { erro?: { codigo: string; mensagem: string } })?.erro;
    return erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." };
  },
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/horarios"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/horarios"
            element={<HorarioPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function logarComo(papel: string) {
  useAuthStore.setState({
    accessToken: "tok",
    refreshToken: "ref",
    usuario: { id: "u1", nome: "Usuario", email: "u@tjr.app", papel },
  });
}

function mockGetPadrao(overrides: Record<string, unknown> = {}) {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return {
        data: { id: "mod-1", nome: "Resgate no Plano", niveis_aplicaveis: [1, 2] },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/rodadas") {
      return {
        data: {
          itens: [
            { id: "rod-1", modalidade_id: "mod-1", numero: 1, status: "AGENDADA" },
            { id: "rod-2", modalidade_id: "mod-1", numero: 2, status: "AGENDADA" },
          ],
          total: 2,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/arenas") {
      return {
        data: {
          itens: (overrides.arenas as unknown[]) ?? [
            { id: "are-1", modalidade_id: "mod-1", nome: "Arena 1", niveis_aplicaveis: null, ativo: true },
          ],
          total: 1,
          page: 1,
          size: 50,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/agendamentos") {
      return {
        data: {
          itens: (overrides.agendamentos as unknown[]) ?? [],
          total: 0,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/agendamentos/estimativa") {
      return {
        data: (overrides.estimativas as unknown[]) ?? [],
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/equipes") {
      return {
        data: {
          itens: [{ id: "eq-1", nome: "Equipe Foguete", nivel: 1, ativo: true }],
          total: 1,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ accessToken: null, refreshToken: null, usuario: null });
});

describe("HorarioPage", () => {
  it("pede a lista de agendamentos com size dentro do limite aceito pela API (le=200)", async () => {
    logarComo("COORDENADOR");
    mockGetPadrao();

    renderPage();
    await screen.findByText("Arena 1");

    const chamadaAgendamentos = (
      vi.mocked(api.GET).mock.calls as unknown as [string, { params: { query: { size: number } } }][]
    ).find(([path]) => path === "/api/v1/agendamentos");
    expect(chamadaAgendamentos?.[1].params.query.size).toBeLessThanOrEqual(200);
  });

  it("lista as arenas cadastradas da modalidade", async () => {
    logarComo("COORDENADOR");
    mockGetPadrao();

    renderPage();

    expect(await screen.findByText("Arena 1")).toBeInTheDocument();
  });

  it("coordenador cria uma arena pelo formulario", async () => {
    logarComo("COORDENADOR");
    mockGetPadrao();
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "are-nova", modalidade_id: "mod-1", nome: "Arena Nova", niveis_aplicaveis: null, ativo: true },
      error: undefined,
    } as never);

    renderPage();
    await screen.findByText("Arena 1");

    await userEvent.type(screen.getByLabelText(/nome da arena/i), "Arena Nova");
    await userEvent.click(screen.getByRole("button", { name: /criar arena/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/arenas",
        expect.objectContaining({
          body: expect.objectContaining({ modalidade_id: "mod-1", nome: "Arena Nova" }),
        }),
      ),
    );
  });

  it("gera horario mandando rodada_ids e horario_inicio corretos", async () => {
    logarComo("COORDENADOR");
    mockGetPadrao();
    vi.mocked(api.POST).mockResolvedValue({ data: [], error: undefined } as never);

    renderPage();
    await screen.findByText("Arena 1");

    await userEvent.click(screen.getByLabelText(/rodada 1/i));
    await userEvent.type(screen.getByLabelText(/hor[aá]rio de in[ií]cio/i), "2026-08-10T08:00");
    await userEvent.click(screen.getByRole("button", { name: /^gerar hor[aá]rio$/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/agendamentos/gerar",
        expect.objectContaining({
          body: expect.objectContaining({
            modalidade_id: "mod-1",
            rodada_ids: ["rod-1"],
          }),
        }),
      ),
    );
  });

  it("erro 409 mostra mensagem inline e botao para gerar mesmo assim", async () => {
    logarComo("COORDENADOR");
    mockGetPadrao();
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "AGENDAMENTO_JA_EXISTE", mensagem: "Ja existe horario gerado." } },
    } as never);

    renderPage();
    await screen.findByText("Arena 1");

    await userEvent.click(screen.getByLabelText(/rodada 1/i));
    await userEvent.type(screen.getByLabelText(/hor[aá]rio de in[ií]cio/i), "2026-08-10T08:00");
    await userEvent.click(screen.getByRole("button", { name: /^gerar hor[aá]rio$/i }));

    expect(await screen.findByText(/ja existe horario gerado/i)).toBeInTheDocument();
    const botaoRegerar = screen.getByRole("button", { name: /gerar mesmo assim/i });

    vi.mocked(api.POST).mockResolvedValue({ data: [], error: undefined } as never);
    await userEvent.click(botaoRegerar);

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/agendamentos/gerar",
        expect.objectContaining({ body: expect.objectContaining({ regenerar: true }) }),
      ),
    );
  });

  it("mostra a agenda gerada agrupada por rodada e arena", async () => {
    logarComo("COORDENADOR");
    mockGetPadrao({
      agendamentos: [
        {
          id: "ag-1",
          rodada_id: "rod-1",
          equipe_id: "eq-1",
          arena_id: "are-1",
          ordem_na_arena: 0,
          horario_inicio: "2026-08-10T08:00:00Z",
        },
      ],
    });

    renderPage();

    const secaoAgenda = (await screen.findByText(/agenda gerada/i)).closest("section")!;
    expect(await within(secaoAgenda).findByText("Arena 1")).toBeInTheDocument();
    expect(within(secaoAgenda).getByText(/equipe foguete/i)).toBeInTheDocument();
    expect(within(secaoAgenda).getByText(/rodada 1/i)).toBeInTheDocument();
  });

  it("mostra o horario previsto da estimativa no lugar do horario planejado, sem badge de atraso", async () => {
    logarComo("COORDENADOR");
    mockGetPadrao({
      agendamentos: [
        {
          id: "ag-1",
          rodada_id: "rod-1",
          equipe_id: "eq-1",
          arena_id: "are-1",
          ordem_na_arena: 0,
          horario_inicio: "2026-08-10T08:00:00Z",
        },
      ],
      estimativas: [{ agendamento_id: "ag-1", horario_previsto: "2026-08-10T08:15:00Z" }],
    });

    renderPage();

    const secaoAgenda = (await screen.findByText(/agenda gerada/i)).closest("section")!;
    await within(secaoAgenda).findByText("Equipe Foguete");

    expect(within(secaoAgenda).queryByText(/05:00/)).not.toBeInTheDocument();
    expect(within(secaoAgenda).getByText(/05:15/)).toBeInTheDocument();
    expect(within(secaoAgenda).queryByText(/atrasad/i)).not.toBeInTheDocument();
  });

  it("esconde os controles de escrita quando o usuario nao e coordenador", async () => {
    logarComo("ARBITRO");
    mockGetPadrao();

    renderPage();
    await screen.findByText("Arena 1");

    expect(screen.queryByLabelText(/nome da arena/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^gerar hor[aá]rio$/i })).not.toBeInTheDocument();
  });
});
