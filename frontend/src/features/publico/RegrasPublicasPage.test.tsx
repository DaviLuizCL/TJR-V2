import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RegrasPublicasPage } from "./RegrasPublicasPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn() },
  baseUrl: "https://tjr.exemplo",
}));

const MODALIDADES = [
  {
    id: "mod-danca",
    nome: "Dança",
    regras: [
      { tipo: "MANUAL", nome_arquivo: "manual.pdf", atualizado_em: "2026-10-20T12:00:00Z" },
      { tipo: "CADERNO_ALUNO", nome_arquivo: "caderno.pdf", atualizado_em: "2026-10-20T12:00:00Z" },
    ],
  },
  {
    id: "mod-sumo",
    nome: "Sumô",
    regras: [
      { tipo: "MANUAL", nome_arquivo: "manual.pdf", atualizado_em: "2026-10-20T12:00:00Z" },
    ],
  },
  { id: "mod-cabo", nome: "Cabo de Guerra", regras: [] },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RegrasPublicasPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockResolvedValue({ data: MODALIDADES, error: undefined } as never);
});

describe("RegrasPublicasPage", () => {
  it("lista no seletor so as modalidades que ja tem algum PDF", async () => {
    renderPage();

    const seletor = await screen.findByLabelText("Modalidade");
    const opcoes = Array.from((seletor as HTMLSelectElement).options).map((o) => o.text);
    expect(opcoes).toContain("Dança");
    expect(opcoes).toContain("Sumô");
    expect(opcoes).not.toContain("Cabo de Guerra");
  });

  it("ao escolher a modalidade mostra os links do manual e do caderninho", async () => {
    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText("Modalidade"), "mod-danca");

    expect(screen.getByRole("link", { name: /manual completo/i })).toHaveAttribute(
      "href",
      "https://tjr.exemplo/api/v1/publico/modalidades/mod-danca/regras/MANUAL",
    );
    expect(screen.getByRole("link", { name: /caderninho do aluno/i })).toHaveAttribute(
      "href",
      "https://tjr.exemplo/api/v1/publico/modalidades/mod-danca/regras/CADERNO_ALUNO",
    );
  });

  it("PDF que ainda nao foi enviado aparece como indisponivel, sem link", async () => {
    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText("Modalidade"), "mod-sumo");

    expect(screen.getByRole("link", { name: /manual completo/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /caderninho do aluno/i })).not.toBeInTheDocument();
    expect(screen.getByText(/ainda não disponível/i)).toBeInTheDocument();
  });

  it("sem nenhum PDF enviado mostra aviso em vez do seletor", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: [{ id: "mod-cabo", nome: "Cabo de Guerra", regras: [] }],
      error: undefined,
    } as never);

    renderPage();

    expect(await screen.findByText(/nenhuma regra publicada ainda/i)).toBeInTheDocument();
    expect(screen.queryByLabelText("Modalidade")).not.toBeInTheDocument();
  });
});
