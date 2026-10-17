import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { PedirAcessoPage } from "./PedirAcessoPage";

vi.mock("../../api/client", () => ({
  api: { POST: vi.fn() },
  extrairErro: (error: unknown) => {
    const erro = (error as { erro?: { codigo: string; mensagem: string } })?.erro;
    return erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." };
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <PedirAcessoPage />
    </MemoryRouter>,
  );
}

async function preencher({ senha = "segredo1", confirmacao = "segredo1" } = {}) {
  await userEvent.type(screen.getByLabelText(/nome completo/i), "Juiz Novo");
  await userEvent.type(screen.getByLabelText(/e-mail/i), "juiz.novo@tjr.app");
  await userEvent.type(screen.getByLabelText(/^senha$/i), senha);
  await userEvent.type(screen.getByLabelText(/repita a senha/i), confirmacao);
  await userEvent.click(screen.getByRole("button", { name: /enviar pedido/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PedirAcessoPage", () => {
  it("envia nome, e-mail e senha pro pedido de acesso", async () => {
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "s1" }, error: undefined } as never);
    renderPage();

    await preencher();

    expect(api.POST).toHaveBeenCalledWith("/api/v1/solicitacoes-acesso", {
      body: { nome: "Juiz Novo", email: "juiz.novo@tjr.app", senha: "segredo1" },
    });
  });

  it("depois de enviar, diz pra avisar a coordenacao e some com o formulario", async () => {
    vi.mocked(api.POST).mockResolvedValue({ data: { id: "s1" }, error: undefined } as never);
    renderPage();

    await preencher();

    expect(await screen.findByText(/pedido enviado/i)).toBeInTheDocument();
    expect(screen.getByText(/avise a coordenação/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enviar pedido/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /voltar pro login/i })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("nao envia se as duas senhas forem diferentes", async () => {
    renderPage();

    await preencher({ confirmacao: "outra-senha" });

    expect(await screen.findByText(/as senhas não são iguais/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("nao envia senha com menos de 6 caracteres", async () => {
    renderPage();

    await preencher({ senha: "123", confirmacao: "123" });

    expect(await screen.findByText(/pelo menos 6/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("explica quando o e-mail ja tem conta", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "EMAIL_JA_CADASTRADO", mensagem: "x" } },
    } as never);
    renderPage();

    await preencher();

    expect(await screen.findByText(/este e-mail já tem conta/i)).toBeInTheDocument();
  });

  it("explica quando ja existe pedido esperando", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "SOLICITACAO_JA_PENDENTE", mensagem: "x" } },
    } as never);
    renderPage();

    await preencher();

    expect(await screen.findByText(/já existe um pedido com este e-mail/i)).toBeInTheDocument();
  });
});
