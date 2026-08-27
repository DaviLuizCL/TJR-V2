import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { AbrirEventoModal } from "./AbrirEventoModal";

vi.mock("../../api/client", () => ({
  api: { POST: vi.fn(), PATCH: vi.fn() },
  extrairErro: (error: unknown) => {
    const erro = (error as { erro?: { codigo: string; mensagem: string } })?.erro;
    return erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." };
  },
}));

const MODALIDADES = [
  { id: "mod-individual", nome: "Resgate no Plano", tipo_disputa: "INDIVIDUAL" },
  { id: "mod-matamata", nome: "Sumô", tipo_disputa: "CONFRONTO" },
  { id: "mod-todoscontratodos", nome: "Cabo de Guerra", tipo_disputa: "CONFRONTO" },
];

function renderModal(onFechar = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AbrirEventoModal modalidades={MODALIDADES} onFechar={onFechar} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AbrirEventoModal", () => {
  it("mostra um campo de horario por modalidade", () => {
    renderModal();

    expect(screen.getByLabelText("Resgate no Plano")).toBeInTheDocument();
    expect(screen.getByLabelText("Sumô")).toBeInTheDocument();
    expect(screen.getByLabelText("Cabo de Guerra")).toBeInTheDocument();
  });

  it("chama o endpoint certo por tipo: chaveamento/gerar pra toda modalidade de confronto (decide mata-mata/todos-contra-todos por nivel sozinho), rodadas/gerar so pra individual", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "r1", numero: 1 },
      error: undefined,
    } as never);

    renderModal();
    await userEvent.click(screen.getByRole("button", { name: /abrir evento/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/chaveamento/gerar",
        expect.objectContaining({ body: { modalidade_id: "mod-matamata" } }),
      ),
    );
    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/chaveamento/gerar",
      expect.objectContaining({ body: { modalidade_id: "mod-todoscontratodos" } }),
    );
    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/rodadas/gerar",
      expect.objectContaining({ body: { modalidade_id: "mod-individual" } }),
    );
    expect(api.POST).not.toHaveBeenCalledWith(
      "/api/v1/chaveamento/gerar",
      expect.objectContaining({ body: { modalidade_id: "mod-individual" } }),
    );
    expect(api.POST).not.toHaveBeenCalledWith(
      "/api/v1/rodadas/gerar",
      expect.objectContaining({ body: { modalidade_id: "mod-matamata" } }),
    );
    expect(api.POST).not.toHaveBeenCalledWith(
      "/api/v1/rodadas/gerar",
      expect.objectContaining({ body: { modalidade_id: "mod-todoscontratodos" } }),
    );
  });

  it("com horario preenchido, aplica o horario na rodada 1 depois de gerar", async () => {
    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      const body = (opts as { body: { modalidade_id: string } }).body;
      if (path === "/api/v1/chaveamento/gerar") {
        return { data: { id: `r1-${body.modalidade_id}`, numero: 1 }, error: undefined } as never;
      }
      return {
        data: [{ id: `r1-${body.modalidade_id}`, numero: 1 }],
        error: undefined,
      } as never;
    });
    vi.mocked(api.PATCH).mockResolvedValue({ data: {}, error: undefined } as never);

    renderModal();

    await userEvent.type(
      screen.getByLabelText("Resgate no Plano"),
      "2026-03-10T08:00",
    );
    await userEvent.click(screen.getByRole("button", { name: /abrir evento/i }));

    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith(
        "/api/v1/rodadas/{rodada_id}",
        expect.objectContaining({
          params: { path: { rodada_id: "r1-mod-individual" } },
          body: { horario_inicio: new Date("2026-03-10T08:00").toISOString() },
        }),
      ),
    );
    // Modalidades sem horario preenchido nao disparam PATCH.
    expect(api.PATCH).not.toHaveBeenCalledWith(
      "/api/v1/rodadas/{rodada_id}",
      expect.objectContaining({ params: { path: { rodada_id: "r1-mod-matamata" } } }),
    );
  });

  it("erro numa modalidade nao impede as outras de serem processadas, e mostra o erro inline", async () => {
    vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
      const body = (opts as { body: { modalidade_id: string } }).body;
      if (body.modalidade_id === "mod-matamata") {
        return {
          data: undefined,
          error: { erro: { codigo: "RODADA_JA_EXISTE", mensagem: "Ja existe rodada gerada." } },
        } as never;
      }
      if (path === "/api/v1/chaveamento/gerar") {
        return { data: { id: `r1-${body.modalidade_id}`, numero: 1 }, error: undefined } as never;
      }
      return {
        data: [{ id: `r1-${body.modalidade_id}`, numero: 1 }],
        error: undefined,
      } as never;
    });

    renderModal();
    await userEvent.click(screen.getByRole("button", { name: /abrir evento/i }));

    const linhaSumo = (await screen.findByText("Ja existe rodada gerada.")).closest("li")!;
    expect(within(linhaSumo).getByText(/ja existe rodada gerada/i)).toBeInTheDocument();

    const linhaIndividual = screen.getByLabelText("Resgate no Plano").closest("li")!;
    await waitFor(() => expect(within(linhaIndividual).getByText("✓")).toBeInTheDocument());
  });

  it("enquanto processa mostra 'Cancelar'; depois de concluir, mostra 'Fechar' e um resumo do resultado", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "r1", numero: 1 },
      error: undefined,
    } as never);

    renderModal();
    expect(screen.getByRole("button", { name: /^cancelar$/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /abrir evento/i }));

    await waitFor(() =>
      expect(screen.getByText(/conclu[ií]do.*3 de 3/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /^fechar$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^cancelar$/i })).not.toBeInTheDocument();
  });

  it("botao cancelar chama onFechar sem enviar nada", async () => {
    const onFechar = vi.fn();
    renderModal(onFechar);

    await userEvent.click(screen.getByRole("button", { name: /cancelar/i }));

    expect(onFechar).toHaveBeenCalled();
    expect(api.POST).not.toHaveBeenCalled();
  });
});
