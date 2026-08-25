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

  it("loga com sucesso, guarda a sessao e navega direto pro evento (competicoes)", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { access_token: "access-123", refresh_token: "refresh-123", token_type: "bearer" },
      error: undefined,
    } as never);
    vi.mocked(api.GET).mockImplementation(((url: string) => {
      if (url === "/api/v1/auth/me") {
        return Promise.resolve({
          data: { id: "u1", nome: "Coord", email: "coord@tjr.app", papel: "COORDENADOR" },
          error: undefined,
        });
      }
      if (url === "/api/v1/eventos") {
        return Promise.resolve({
          data: { itens: [{ id: "evt-1", nome: "TJR 2026", ano: 2026, status: "EM_ANDAMENTO" }] },
          error: undefined,
        });
      }
      throw new Error(`GET inesperado: ${url}`);
    }) as never);

    renderPage();

    await userEvent.type(screen.getByLabelText(/e-mail/i), "coord@tjr.app");
    await userEvent.type(screen.getByLabelText(/senha/i), "senha-123");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/eventos/evt-1/competicoes"));
    expect(useAuthStore.getState().accessToken).toBe("access-123");
    expect(useAuthStore.getState().usuario?.papel).toBe("COORDENADOR");
  });

  it("loga com sucesso mas sem evento cadastrado ainda, navega para /eventos", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { access_token: "access-123", refresh_token: "refresh-123", token_type: "bearer" },
      error: undefined,
    } as never);
    vi.mocked(api.GET).mockImplementation(((url: string) => {
      if (url === "/api/v1/auth/me") {
        return Promise.resolve({
          data: { id: "u1", nome: "Coord", email: "coord@tjr.app", papel: "COORDENADOR" },
          error: undefined,
        });
      }
      if (url === "/api/v1/eventos") {
        return Promise.resolve({ data: { itens: [] }, error: undefined });
      }
      throw new Error(`GET inesperado: ${url}`);
    }) as never);

    renderPage();

    await userEvent.type(screen.getByLabelText(/e-mail/i), "coord@tjr.app");
    await userEvent.type(screen.getByLabelText(/senha/i), "senha-123");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/eventos"));
  });

  it("permite mostrar e ocultar a senha digitada", async () => {
    renderPage();

    const campoSenha = screen.getByLabelText(/senha/i) as HTMLInputElement;
    await userEvent.type(campoSenha, "senha-secreta");
    expect(campoSenha.type).toBe("password");

    await userEvent.click(screen.getByRole("button", { name: /mostrar/i }));
    expect(campoSenha.type).toBe("text");
    expect(campoSenha.value).toBe("senha-secreta");

    await userEvent.click(screen.getByRole("button", { name: /ocultar/i }));
    expect(campoSenha.type).toBe("password");
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
