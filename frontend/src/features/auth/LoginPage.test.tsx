import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { LoginPage } from "./LoginPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const original = await importOriginal<typeof import("react-router-dom")>();
  return { ...original, useNavigate: () => navigateMock };
});

vi.mock("../../api/client", () => ({
  api: { POST: vi.fn(), GET: vi.fn() },
  extrairErro: (error: unknown) => {
    const erro = (error as { erro?: { codigo: string; mensagem: string } })?.erro;
    return erro ?? { codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." };
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ accessToken: null, refreshToken: null, usuario: null });
});

describe("LoginPage", () => {
  it("renderiza campos de email e senha", () => {
    renderPage();

    expect(screen.getByLabelText(/e-mail/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/senha/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /entrar/i })).toBeInTheDocument();
  });

  it("mostra erro de validacao ao submeter vazio", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));

    expect(await screen.findByText(/informe um e-mail valido/i)).toBeInTheDocument();
  });

  it("loga com sucesso, guarda a sessao e navega para /eventos", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { access_token: "access-123", refresh_token: "refresh-123", token_type: "bearer" },
      error: undefined,
    } as never);
    vi.mocked(api.GET).mockResolvedValue({
      data: { id: "u1", nome: "Coord", email: "coord@tjr.app", papel: "COORDENADOR" },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.type(screen.getByLabelText(/e-mail/i), "coord@tjr.app");
    await userEvent.type(screen.getByLabelText(/senha/i), "senha-123");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/eventos"));
    expect(useAuthStore.getState().accessToken).toBe("access-123");
    expect(useAuthStore.getState().usuario?.papel).toBe("COORDENADOR");
  });

  it("mostra a mensagem de erro quando o login falha", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "CREDENCIAIS_INVALIDAS", mensagem: "Email ou senha invalidos." } },
    } as never);

    renderPage();

    await userEvent.type(screen.getByLabelText(/e-mail/i), "coord@tjr.app");
    await userEvent.type(screen.getByLabelText(/senha/i), "senha-errada");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));

    expect(await screen.findByText(/email ou senha invalidos/i)).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
