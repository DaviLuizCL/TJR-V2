import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { ImportarEquipesPage } from "./ImportarEquipesPage";

vi.mock("../../api/client", () => ({
  api: { POST: vi.fn() },
  extrairErro: (e: { erro?: { mensagem?: string } }) => ({
    codigo: "X",
    mensagem: e?.erro?.mensagem ?? "Ocorreu um erro inesperado.",
  }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/eventos/evt-1/admin/importar"]}>
        <Routes>
          <Route path="/eventos/:eventoId/admin/importar" element={<ImportarEquipesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const RELATORIO = {
  simulacao: true,
  linhas: 10,
  equipes_novas: 7,
  inscricoes_novas: 9,
  ignoradas: 1,
  erros: ["Linha 4: nivel invalido 'abc'."],
};

const ARQUIVO = new File(["conteudo"], "lista.xlsx", {
  type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.POST).mockResolvedValue({ data: RELATORIO, error: undefined } as never);
});

function ultimaQuery() {
  const chamadas = vi.mocked(api.POST).mock.calls;
  const chamada = chamadas[chamadas.length - 1];
  return (chamada[1] as { params: { query: Record<string, unknown> } }).params.query;
}

describe("ImportarEquipesPage", () => {
  it("botao de previa so habilita depois de escolher o arquivo", async () => {
    renderPage();

    expect(screen.getByRole("button", { name: /ver pr[eé]via/i })).toBeDisabled();
    await userEvent.upload(screen.getByLabelText(/planilha/i), ARQUIVO);
    expect(screen.getByRole("button", { name: /ver pr[eé]via/i })).toBeEnabled();
  });

  it("previa chama a API em modo simulacao e mostra o relatorio", async () => {
    renderPage();
    await userEvent.upload(screen.getByLabelText(/planilha/i), ARQUIVO);

    await userEvent.click(screen.getByRole("button", { name: /ver pr[eé]via/i }));

    expect(api.POST).toHaveBeenCalledWith(
      "/api/v1/admin/importar-equipes",
      expect.objectContaining({ body: expect.any(FormData) }),
    );
    expect(ultimaQuery()).toEqual({ evento_id: "evt-1", simular: true });
    expect(await screen.findByText(/7 equipes novas/i)).toBeInTheDocument();
    expect(screen.getByText(/9 inscri[cç][oõ]es novas/i)).toBeInTheDocument();
    expect(screen.getByText("Linha 4: nivel invalido 'abc'.")).toBeInTheDocument();
  });

  it("confirmar depois da previa importa de verdade", async () => {
    renderPage();
    await userEvent.upload(screen.getByLabelText(/planilha/i), ARQUIVO);
    await userEvent.click(screen.getByRole("button", { name: /ver pr[eé]via/i }));
    await screen.findByText(/7 equipes novas/i);

    vi.mocked(api.POST).mockResolvedValue({
      data: { ...RELATORIO, simulacao: false },
      error: undefined,
    } as never);
    await userEvent.click(screen.getByRole("button", { name: /confirmar importa[cç][aã]o/i }));

    expect(ultimaQuery()).toEqual({ evento_id: "evt-1", simular: false });
    expect(await screen.findByText(/importa[cç][aã]o conclu[ií]da/i)).toBeInTheDocument();
  });

  it("nao mostra confirmar antes da previa", async () => {
    renderPage();
    await userEvent.upload(screen.getByLabelText(/planilha/i), ARQUIVO);

    expect(screen.queryByRole("button", { name: /confirmar importa/i })).toBeNull();
  });

  it("mostra erro quando o arquivo e invalido", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: undefined,
      error: { erro: { mensagem: "O arquivo enviado nao e uma planilha .xlsx valida." } },
    } as never);
    renderPage();
    await userEvent.upload(screen.getByLabelText(/planilha/i), ARQUIVO);

    await userEvent.click(screen.getByRole("button", { name: /ver pr[eé]via/i }));

    expect(await screen.findByText(/nao e uma planilha/i)).toBeInTheDocument();
  });
});
