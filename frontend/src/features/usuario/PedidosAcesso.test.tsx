import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PedidosAcesso } from "./PedidosAcesso";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

const PEDIDOS = [
  {
    id: "s1",
    nome: "Maria Juíza",
    email: "maria@tjr.app",
    status: "PENDENTE",
    criado_em: "2026-10-17T19:30:00Z",
  },
  {
    id: "s2",
    nome: "João Juiz",
    email: "joao@tjr.app",
    status: "PENDENTE",
    criado_em: "2026-10-17T19:40:00Z",
  },
];

function renderComponente() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <PedidosAcesso />
    </QueryClientProvider>,
  );
}

function card(nome: string) {
  return screen.getByText(nome).closest("li") as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockResolvedValue({ data: PEDIDOS, error: undefined } as never);
  vi.mocked(api.POST).mockResolvedValue({ data: {}, error: undefined } as never);
});

describe("PedidosAcesso", () => {
  it("mostra um card por pedido com nome, e-mail e horario em Fortaleza", async () => {
    renderComponente();

    expect(await screen.findByText("Maria Juíza")).toBeInTheDocument();
    expect(within(card("Maria Juíza")).getByText("maria@tjr.app")).toBeInTheDocument();
    expect(within(card("Maria Juíza")).getByText(/17\/10.*16:30/)).toBeInTheDocument();
    expect(screen.getByText("João Juiz")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /pedidos de acesso \(2\)/i })).toBeInTheDocument();
  });

  it("aprovar pede confirmacao e cria a conta como juiz", async () => {
    renderComponente();
    await screen.findByText("Maria Juíza");

    await userEvent.click(within(card("Maria Juíza")).getByRole("button", { name: /^aprovar$/i }));
    expect(api.POST).not.toHaveBeenCalled();

    await userEvent.click(
      within(card("Maria Juíza")).getByRole("button", { name: /criar como juiz/i }),
    );

    expect(api.POST).toHaveBeenCalledWith("/api/v1/solicitacoes-acesso/{solicitacao_id}/aprovar", {
      params: { path: { solicitacao_id: "s1" } },
      body: { papel: "ARBITRO" },
    });
    expect(await screen.findByText(/conta de juiz de maria juíza criada/i)).toBeInTheDocument();
  });

  it("aprovar tambem pode criar a conta como coordenador, avisando que mexe em tudo", async () => {
    renderComponente();
    await screen.findByText("Maria Juíza");

    await userEvent.click(within(card("Maria Juíza")).getByRole("button", { name: /^aprovar$/i }));
    expect(within(card("Maria Juíza")).getByText(/coordenador pode mexer em tudo/i)).toBeInTheDocument();
    await userEvent.click(
      within(card("Maria Juíza")).getByRole("button", { name: /criar como coordenador/i }),
    );

    expect(api.POST).toHaveBeenCalledWith("/api/v1/solicitacoes-acesso/{solicitacao_id}/aprovar", {
      params: { path: { solicitacao_id: "s1" } },
      body: { papel: "COORDENADOR" },
    });
    expect(
      await screen.findByText(/conta de coordenador de maria juíza criada/i),
    ).toBeInTheDocument();
  });

  it("recusar pede confirmacao e chama a rota de recusa", async () => {
    renderComponente();
    await screen.findByText("João Juiz");

    await userEvent.click(within(card("João Juiz")).getByRole("button", { name: /^recusar$/i }));
    expect(api.POST).not.toHaveBeenCalled();
    await userEvent.click(within(card("João Juiz")).getByRole("button", { name: /sim, recusar/i }));

    expect(api.POST).toHaveBeenCalledWith("/api/v1/solicitacoes-acesso/{solicitacao_id}/recusar", {
      params: { path: { solicitacao_id: "s2" } },
    });
  });

  it("cancelar a confirmacao nao faz nada", async () => {
    renderComponente();
    await screen.findByText("Maria Juíza");

    await userEvent.click(within(card("Maria Juíza")).getByRole("button", { name: /^aprovar$/i }));
    await userEvent.click(within(card("Maria Juíza")).getByRole("button", { name: /cancelar/i }));

    expect(api.POST).not.toHaveBeenCalled();
    expect(within(card("Maria Juíza")).getByRole("button", { name: /^aprovar$/i })).toBeInTheDocument();
  });

  it("lembra de conferir no grupo antes de aprovar", async () => {
    renderComponente();

    expect(await screen.findByText(/confira no grupo dos juízes/i)).toBeInTheDocument();
  });

  it("sem pedidos, explica como o juiz pede acesso", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: [], error: undefined } as never);
    renderComponente();

    expect(await screen.findByText(/nenhum pedido esperando/i)).toBeInTheDocument();
    expect(screen.getByText(/sou juiz e ainda não tenho conta/i)).toBeInTheDocument();
  });

  it("mostra erro se a aprovacao falhar", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "X", mensagem: "x" } },
    } as never);
    renderComponente();
    await screen.findByText("Maria Juíza");

    await userEvent.click(within(card("Maria Juíza")).getByRole("button", { name: /^aprovar$/i }));
    await userEvent.click(
      within(card("Maria Juíza")).getByRole("button", { name: /criar como juiz/i }),
    );

    expect(await screen.findByText("Ocorreu um erro inesperado.")).toBeInTheDocument();
  });
});
