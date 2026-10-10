import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { UsuarioListPage } from "./UsuarioListPage";

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
      <UsuarioListPage />
    </QueryClientProvider>,
  );
}

function mockGet(usuarios: unknown[] = []) {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/usuarios") {
      return {
        data: { itens: usuarios, total: usuarios.length, page: 1, size: 50 },
        error: undefined,
      } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("UsuarioListPage", () => {
  it("lista os usuarios cadastrados com nome, email e papel", async () => {
    mockGet([
      { id: "u1", nome: "Joana Arbitra", email: "joana@tjr.app", papel: "ARBITRO", ativo: true },
    ]);

    renderPage();

    const linha = (await screen.findByText("Joana Arbitra")).closest("li")!;
    expect(within(linha).getByText("joana@tjr.app")).toBeInTheDocument();
    expect(within(linha).getByText("ARBITRO")).toBeInTheDocument();
  });

  it("mostra mensagem quando nao ha nenhum usuario alem de quem esta logado", async () => {
    mockGet([]);

    renderPage();

    expect(await screen.findByText(/nenhum usu[aá]rio/i)).toBeInTheDocument();
  });

  it("cadastra um novo usuario com os dados do formulario", async () => {
    mockGet([]);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "u2", nome: "Novo Arbitro", email: "novo@tjr.app", papel: "ARBITRO", ativo: true },
      error: undefined,
    } as never);

    renderPage();

    await userEvent.type(await screen.findByLabelText(/^nome$/i), "Novo Arbitro");
    await userEvent.type(screen.getByLabelText(/^e-?mail$/i), "novo@tjr.app");
    await userEvent.type(screen.getByLabelText(/^senha$/i), "senha-forte");
    await userEvent.selectOptions(screen.getByLabelText(/^papel$/i), "ARBITRO");
    await userEvent.click(screen.getByRole("button", { name: /cadastrar/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/usuarios",
        expect.objectContaining({
          body: {
            nome: "Novo Arbitro",
            email: "novo@tjr.app",
            senha: "senha-forte",
            papel: "ARBITRO",
          },
        }),
      ),
    );
  });

  it("limpa o formulario depois de cadastrar com sucesso", async () => {
    mockGet([]);
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "u2", nome: "Novo Arbitro", email: "novo@tjr.app", papel: "ARBITRO", ativo: true },
      error: undefined,
    } as never);

    renderPage();

    const campoNome = (await screen.findByLabelText(/^nome$/i)) as HTMLInputElement;
    await userEvent.type(campoNome, "Novo Arbitro");
    await userEvent.type(screen.getByLabelText(/^e-?mail$/i), "novo@tjr.app");
    await userEvent.type(screen.getByLabelText(/^senha$/i), "senha-forte");
    await userEvent.click(screen.getByRole("button", { name: /cadastrar/i }));

    await waitFor(() => expect(campoNome.value).toBe(""));
  });

  it("permite mostrar e ocultar a senha digitada no cadastro", async () => {
    mockGet([]);

    renderPage();

    const campoSenha = (await screen.findByLabelText(/^senha$/i)) as HTMLInputElement;
    await userEvent.type(campoSenha, "senha-forte");
    expect(campoSenha.type).toBe("password");

    await userEvent.click(screen.getByRole("button", { name: /mostrar/i }));
    expect(campoSenha.type).toBe("text");
    expect(campoSenha.value).toBe("senha-forte");

    await userEvent.click(screen.getByRole("button", { name: /ocultar/i }));
    expect(campoSenha.type).toBe("password");
  });

  it("mostra erro quando o cadastro falha (ex.: email duplicado)", async () => {
    mockGet([]);
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { codigo: "EMAIL_JA_CADASTRADO", mensagem: "Ja existe um usuario com este email." } },
    } as never);

    renderPage();

    await userEvent.type(await screen.findByLabelText(/^nome$/i), "Duplicado");
    await userEvent.type(screen.getByLabelText(/^e-?mail$/i), "duplicado@tjr.app");
    await userEvent.type(screen.getByLabelText(/^senha$/i), "senha-forte");
    await userEvent.click(screen.getByRole("button", { name: /cadastrar/i }));

    expect(await screen.findByText(/ja existe um usuario com este email/i)).toBeInTheDocument();
  });

  describe("editar usuario", () => {
    const JOANA = {
      id: "u1",
      nome: "Joana Arbitra",
      email: "joana@tjr.app",
      papel: "ARBITRO",
      ativo: true,
    };

    async function abrirEdicao(usuario = JOANA) {
      mockGet([usuario]);
      renderPage();
      const linha = (await screen.findByText(usuario.nome)).closest("li")!;
      await userEvent.click(within(linha).getByRole("button", { name: /editar/i }));
      return linha;
    }

    beforeEach(() => {
      vi.mocked(api.PATCH).mockResolvedValue({ data: {}, error: undefined } as never);
      vi.mocked(api.POST).mockResolvedValue({ data: undefined, error: undefined } as never);
    });

    it("desativa a conta", async () => {
      const linha = await abrirEdicao();

      await userEvent.click(within(linha).getByRole("button", { name: /desativar conta/i }));

      expect(api.PATCH).toHaveBeenCalledWith("/api/v1/usuarios/{usuario_id}", {
        params: { path: { usuario_id: "u1" } },
        body: { ativo: false },
      });
    });

    it("conta inativa mostra opcao de reativar", async () => {
      const linha = await abrirEdicao({ ...JOANA, ativo: false });

      await userEvent.click(within(linha).getByRole("button", { name: /reativar conta/i }));

      expect(api.PATCH).toHaveBeenCalledWith("/api/v1/usuarios/{usuario_id}", {
        params: { path: { usuario_id: "u1" } },
        body: { ativo: true },
      });
    });

    it("troca a senha", async () => {
      const linha = await abrirEdicao();

      await userEvent.type(within(linha).getByLabelText(/nova senha/i), "senha-nova");
      await userEvent.click(within(linha).getByRole("button", { name: /salvar senha/i }));

      expect(api.POST).toHaveBeenCalledWith("/api/v1/usuarios/{usuario_id}/senha", {
        params: { path: { usuario_id: "u1" } },
        body: { senha: "senha-nova" },
      });
      expect(await within(linha).findByText(/senha trocada/i)).toBeInTheDocument();
    });

    it("nao deixa salvar senha com menos de 6 caracteres", async () => {
      const linha = await abrirEdicao();

      await userEvent.type(within(linha).getByLabelText(/nova senha/i), "123");

      expect(within(linha).getByRole("button", { name: /salvar senha/i })).toBeDisabled();
    });

    it("muda o papel", async () => {
      const linha = await abrirEdicao();

      await userEvent.selectOptions(within(linha).getByLabelText(/mudar papel/i), "SECRETARIA");
      await userEvent.click(within(linha).getByRole("button", { name: /salvar papel/i }));

      expect(api.PATCH).toHaveBeenCalledWith("/api/v1/usuarios/{usuario_id}", {
        params: { path: { usuario_id: "u1" } },
        body: { papel: "SECRETARIA" },
      });
    });

    it("mostra o erro quando a API recusa (ex.: tentar se desativar)", async () => {
      vi.mocked(api.PATCH).mockResolvedValue({
        data: undefined,
        error: {
          erro: { codigo: "NAO_PODE_ALTERAR_PROPRIO_ACESSO", mensagem: "Voce nao pode desativar a propria conta." },
        },
      } as never);
      const linha = await abrirEdicao();

      await userEvent.click(within(linha).getByRole("button", { name: /desativar conta/i }));

      expect(await within(linha).findByText(/nao pode desativar a propria conta/i)).toBeInTheDocument();
    });
  });
});
