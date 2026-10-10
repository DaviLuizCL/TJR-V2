import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { OrdemApresentacaoPage } from "./OrdemApresentacaoPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/modalidades/mod-1/ordem"]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/ordem"
            element={<OrdemApresentacaoPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const EQUIPES = [
  { id: "eq-a", nome: "Alfa", nivel: 1, ativo: true },
  { id: "eq-b", nome: "Beta", nivel: 1, ativo: true },
  { id: "eq-c", nome: "Gama", nivel: 1, ativo: true },
  { id: "eq-d", nome: "Delta", nivel: 2, ativo: true },
];

function mockGet(ordens: Record<string, number | null> = {}) {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return { data: { id: "mod-1", nome: "Dança", tipo_disputa: "INDIVIDUAL" } } as never;
    }
    if (path === "/api/v1/inscricoes") {
      const itens = EQUIPES.map((e) => ({
        id: `ins-${e.id}`,
        equipe_id: e.id,
        modalidade_id: "mod-1",
        ordem_apresentacao: ordens[e.id] ?? null,
      }));
      return { data: { itens, total: itens.length, page: 1, size: 1000 } } as never;
    }
    if (path === "/api/v1/equipes") {
      return { data: { itens: EQUIPES, total: EQUIPES.length, page: 1, size: 1000 } } as never;
    }
    return { data: undefined } as never;
  });
}

function logarComo(papel: string) {
  useAuthStore.setState({
    accessToken: "tok",
    refreshToken: "tok",
    usuario: { id: "u1", nome: "Usuario Teste", email: "user@tjr.app", papel },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  logarComo("COORDENADOR");
  vi.mocked(api.POST).mockResolvedValue({ data: undefined, error: undefined } as never);
  vi.mocked(api.PUT).mockResolvedValue({ data: undefined, error: undefined } as never);
});

function nomesDaSecao(secao: HTMLElement): string[] {
  return within(secao)
    .getAllByRole("listitem")
    .map((li) => within(li).getByTestId("nome-equipe").textContent ?? "");
}

describe("OrdemApresentacaoPage", () => {
  it("mostra uma secao por nivel com as equipes na ordem sorteada", async () => {
    mockGet({ "eq-a": 2, "eq-b": 3, "eq-c": 1, "eq-d": 1 });

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    expect(nomesDaSecao(nivel1)).toEqual(["Gama", "Alfa", "Beta"]);
    expect(screen.getByRole("region", { name: /n[ií]vel 2/i })).toBeInTheDocument();
  });

  it("avisa quando o nivel ainda nao tem ordem sorteada", async () => {
    mockGet();

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    expect(within(nivel1).getByText(/ordem ainda n[aã]o foi sorteada/i)).toBeInTheDocument();
  });

  it("sorteia a ordem do nivel direto quando ainda nao existe ordem", async () => {
    mockGet();

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    await userEvent.click(within(nivel1).getByRole("button", { name: /sortear ordem/i }));

    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/modalidades/{modalidade_id}/ordem-apresentacao/sortear",
      expect.objectContaining({
        params: { path: { modalidade_id: "mod-1" } },
        body: { nivel: 1 },
      }),
    );
  });

  it("pede confirmacao antes de sortear de novo um nivel que ja tem ordem", async () => {
    mockGet({ "eq-a": 1, "eq-b": 2, "eq-c": 3 });

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    await userEvent.click(within(nivel1).getByRole("button", { name: /sortear de novo/i }));
    expect(api.POST).not.toHaveBeenCalled();

    await userEvent.click(within(nivel1).getByRole("button", { name: /sim, sortear de novo/i }));
    expect(api.POST).toHaveBeenCalledTimes(1);
  });

  it("subir uma equipe salva a nova ordem do nivel", async () => {
    mockGet({ "eq-a": 1, "eq-b": 2, "eq-c": 3 });

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    await userEvent.click(within(nivel1).getByRole("button", { name: /subir beta/i }));

    expect(api.PUT).toHaveBeenCalledWith(
      "/api/v1/modalidades/{modalidade_id}/ordem-apresentacao",
      expect.objectContaining({
        body: { nivel: 1, equipe_ids: ["eq-b", "eq-a", "eq-c"] },
      }),
    );
  });

  it("descer uma equipe salva a nova ordem do nivel", async () => {
    mockGet({ "eq-a": 1, "eq-b": 2, "eq-c": 3 });

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    await userEvent.click(within(nivel1).getByRole("button", { name: /descer alfa/i }));

    expect(api.PUT).toHaveBeenCalledWith(
      "/api/v1/modalidades/{modalidade_id}/ordem-apresentacao",
      expect.objectContaining({
        body: { nivel: 1, equipe_ids: ["eq-b", "eq-a", "eq-c"] },
      }),
    );
  });

  it("primeira equipe nao pode subir e ultima nao pode descer", async () => {
    mockGet({ "eq-a": 1, "eq-b": 2, "eq-c": 3 });

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    expect(within(nivel1).getByRole("button", { name: /subir alfa/i })).toBeDisabled();
    expect(within(nivel1).getByRole("button", { name: /descer gama/i })).toBeDisabled();
  });

  it("titulo da pagina fala em sequencia de competicao", async () => {
    mockGet();

    renderPage();

    expect(
      await screen.findByRole("heading", { level: 1, name: /sequ[eê]ncia de competi[cç][aã]o/i }),
    ).toBeInTheDocument();
  });

  it("botao de PDF pro telao baixa o PDF da sequencia", async () => {
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    mockGet({ "eq-a": 1, "eq-b": 2, "eq-c": 3 });
    renderPage();
    await screen.findByRole("region", { name: /absoluto/i });
    vi.mocked(api.GET).mockResolvedValueOnce({ data: new Blob(["%PDF"]), error: undefined } as never);

    await userEvent.click(screen.getByRole("button", { name: /pdf pro tel[aã]o/i }));

    expect(api.GET).toHaveBeenCalledWith(
      "/api/v1/modalidades/{modalidade_id}/sequencia-competicao.pdf",
      { params: { path: { modalidade_id: "mod-1" } }, parseAs: "blob" },
    );
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("arbitro tambem pode gerar o PDF pro telao", async () => {
    logarComo("ARBITRO");
    mockGet({ "eq-a": 1, "eq-b": 2, "eq-c": 3 });

    renderPage();

    expect(await screen.findByRole("button", { name: /pdf pro tel[aã]o/i })).toBeInTheDocument();
  });

  it("arbitro ve a ordem mas nao ve botoes de sortear nem de mover", async () => {
    logarComo("ARBITRO");
    mockGet({ "eq-a": 1, "eq-b": 2, "eq-c": 3 });

    renderPage();

    const nivel1 = await screen.findByRole("region", { name: /absoluto/i });
    expect(nomesDaSecao(nivel1)).toEqual(["Alfa", "Beta", "Gama"]);
    expect(within(nivel1).queryByRole("button")).not.toBeInTheDocument();
  });
});
