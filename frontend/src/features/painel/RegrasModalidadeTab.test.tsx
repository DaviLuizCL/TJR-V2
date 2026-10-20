import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { RegrasModalidadeTab } from "./RegrasModalidadeTab";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
  baseUrl: "https://tjr.exemplo",
  extrairErro: () => ({ codigo: "ARQUIVO_NAO_E_PDF", mensagem: "O arquivo precisa ser um PDF." }),
}));

function logarComo(papel: string) {
  useAuthStore.setState({
    accessToken: "tok",
    refreshToken: "tok",
    usuario: { id: "u1", nome: "Usuario Teste", email: "user@tjr.app", papel },
  });
}

function renderTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RegrasModalidadeTab />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const pdf = () => new File(["%PDF-1.4"], "manual-danca.pdf", { type: "application/pdf" });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockResolvedValue({
    data: [
      {
        id: "mod-danca",
        nome: "Dança",
        regras: [
          {
            tipo: "CADERNO_ALUNO",
            nome_arquivo: "caderno-danca.pdf",
            atualizado_em: "2026-10-20T12:00:00Z",
          },
        ],
      },
    ],
    error: undefined,
  } as never);
  vi.mocked(api.PUT).mockResolvedValue({ data: {}, error: undefined } as never);
  vi.mocked(api.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);
});

describe("RegrasModalidadeTab", () => {
  it("mostra por modalidade o que ja foi enviado e o que falta", async () => {
    logarComo("COORDENADOR");
    renderTab();

    const secao = await screen.findByRole("region", { name: "Dança" });
    expect(within(secao).getByText("caderno-danca.pdf")).toBeInTheDocument();
    expect(within(secao).getByText(/nenhum pdf enviado/i)).toBeInTheDocument();
    expect(within(secao).getByRole("link", { name: /ver/i })).toHaveAttribute(
      "href",
      "https://tjr.exemplo/api/v1/publico/modalidades/mod-danca/regras/CADERNO_ALUNO",
    );
  });

  it("coordenador envia o PDF do manual completo", async () => {
    logarComo("COORDENADOR");
    renderTab();

    await userEvent.upload(
      await screen.findByLabelText("Enviar Manual completo de Dança"),
      pdf(),
    );

    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/regras/{tipo}",
        expect.objectContaining({
          params: { path: { modalidade_id: "mod-danca", tipo: "MANUAL" } },
          body: expect.any(FormData),
        }),
      ),
    );
    const corpo = vi.mocked(api.PUT).mock.calls[0][1] as unknown as { body: FormData };
    expect((corpo.body.get("arquivo") as File).name).toBe("manual-danca.pdf");
  });

  it("mostra o erro quando o envio e recusado", async () => {
    logarComo("COORDENADOR");
    vi.mocked(api.PUT).mockResolvedValue({ data: undefined, error: { erro: {} } } as never);
    renderTab();

    await userEvent.upload(
      await screen.findByLabelText("Enviar Manual completo de Dança"),
      pdf(),
    );

    expect(await screen.findByText("O arquivo precisa ser um PDF.")).toBeInTheDocument();
  });

  it("remover pede confirmacao antes de apagar", async () => {
    logarComo("COORDENADOR");
    renderTab();

    await userEvent.click(await screen.findByRole("button", { name: /remover/i }));
    expect(api.DELETE).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /sim, remover/i }));

    await waitFor(() =>
      expect(api.DELETE).toHaveBeenCalledWith(
        "/api/v1/modalidades/{modalidade_id}/regras/{tipo}",
        { params: { path: { modalidade_id: "mod-danca", tipo: "CADERNO_ALUNO" } } },
      ),
    );
  });

  it("quem nao e coordenador so ve, sem enviar nem remover", async () => {
    logarComo("SECRETARIA");
    renderTab();

    await screen.findByRole("region", { name: "Dança" });
    expect(screen.queryByLabelText(/enviar/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /remover/i })).not.toBeInTheDocument();
  });
});
