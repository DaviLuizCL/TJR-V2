import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { db } from "../../lib/db";
import { queryClient } from "../../lib/query-client";
import { _resetarSincronizacaoParaTeste } from "../../lib/sync";
import { LancamentoFormPage } from "./LancamentoFormPage";

vi.mock("../../api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  extrairErro: () => ({ codigo: "ERRO_DESCONHECIDO", mensagem: "Ocorreu um erro inesperado." }),
}));

function TelaDePontuar() {
  const location = useLocation();
  return <div>TELA DE PONTUAR{location.search}</div>;
}

// sync.ts invalida queries no queryClient global (o mesmo usado em produção
// via main.tsx) - os testes usam essa mesma instancia em vez de criar uma
// local, senao a invalidacao do sync nunca alcancaria o cache que a tela
// esta observando.
function renderPage(caminho = "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo") {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[caminho]}>
        <Routes>
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas/:rodadaId/lancamentos/novo"
            element={<LancamentoFormPage />}
          />
          <Route
            path="/eventos/:eventoId/modalidades/:modalidadeId/pontuar"
            element={<TelaDePontuar />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const FICHA_COMPLETA = {
  id: "ficha-1",
  modalidade_id: "mod-1",
  nivel: null,
  grupos: [
    {
      id: "grupo-1",
      nome: "Geral",
      criterios: [
        {
          id: "crit-1",
          nome: "Lombada",
          categoria: "PONTUACAO",
          tipo: "CONTADOR",
          pontos: 10,
          valores_permitidos: null,
          max_ocorrencias: null,
          modificador_tipo: null,
          modificador_valor: null,
        },
      ],
    },
  ],
};

function mockGet() {
  vi.mocked(api.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/rodadas/{rodada_id}") {
      return {
        data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/modalidades/{modalidade_id}") {
      return {
        data: {
          id: "mod-1",
          nome: "Sumo",
          ficha_unica_entre_niveis: true,
          tentativas_por_rodada: 1,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/inscricoes") {
      return {
        data: {
          itens: [
            { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
            { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
          ],
          total: 2,
          page: 1,
          size: 100,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/equipes") {
      return {
        data: {
          itens: [
            { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
            { id: "eq-2", nome: "Equipe Y", nivel: 3, ativo: true },
          ],
          total: 2,
          page: 1,
          size: 200,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/fichas") {
      return {
        data: {
          itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
          total: 1,
          page: 1,
          size: 100,
        },
        error: undefined,
      } as never;
    }
    if (path === "/api/v1/fichas/{ficha_id}") {
      return { data: FICHA_COMPLETA, error: undefined } as never;
    }
    if (path === "/api/v1/lancamentos") {
      return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
    }
    return { data: undefined, error: undefined } as never;
  });
}

beforeEach(async () => {
  vi.clearAllMocks();
  await db.lancamentoOutbox.clear();
  queryClient.clear();
  _resetarSincronizacaoParaTeste();
});

describe("LancamentoFormPage", () => {
  it("mostra os criterios da ficha depois de escolher a equipe", async () => {
    mockGet();

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/equipe/i), "eq-1");

    expect(await screen.findByText("Lombada")).toBeInTheDocument();
  });

  it("registra o lancamento com os itens preenchidos e mostra o total persistido", async () => {
    mockGet();
    vi.mocked(api.POST).mockImplementation(async (path: string) => {
      if (path === "/api/v1/fichas/{ficha_id}/simular") {
        return { data: { total: 30 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            id: "lanc-1",
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            tentativa: 1,
            revision: 1,
            status: "PENDENTE",
            total: 30,
            itens: [],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/equipe/i), "eq-1");
    await screen.findByText("Lombada");
    await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
    await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            itens: [{ criterio_id: "crit-1", ocorrencias: 1 }],
          }),
        }),
      ),
    );

    const blocoTotal = (await screen.findByText(/total persistido/i)).closest("div")!;
    expect(within(blocoTotal).getByText("30")).toBeInTheDocument();
  });

  it("confirma o lancamento depois de criado", async () => {
    mockGet();
    vi.mocked(api.POST).mockImplementation(async (path: string) => {
      if (path === "/api/v1/fichas/{ficha_id}/simular") {
        return { data: { total: 10 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            id: "lanc-1",
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            tentativa: 1,
            revision: 1,
            status: "PENDENTE",
            total: 10,
            itens: [],
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        return {
          data: {
            id: "lanc-1",
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            tentativa: 1,
            revision: 1,
            status: "CONFIRMADO",
            total: 10,
            itens: [],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/equipe/i), "eq-1");
    await screen.findByText("Lombada");
    await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
    await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));

    await screen.findByText(/total persistido/i);
    await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos/{lancamento_id}/confirmar",
        expect.objectContaining({ params: { path: { lancamento_id: "lanc-1" } } }),
      ),
    );
    // Depois de confirmado, o formulario reseta pra receber a proxima equipe
    // (ver testes dedicados de reset/filtro mais abaixo).
    await waitFor(() => {
      const select = screen.getByLabelText(/equipe/i) as HTMLSelectElement;
      expect(select.value).toBe("");
    });
  });

  it("nao mostra seletor de tentativa quando a modalidade tem so uma tentativa por rodada", async () => {
    mockGet();

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/equipe/i), "eq-1");
    await screen.findByText("Lombada");

    expect(screen.queryByLabelText(/tentativa/i)).not.toBeInTheDocument();
  });

  it("mostra seletor de tentativa e envia a escolhida quando ha mais de uma por rodada", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: {
            id: "mod-1",
            nome: "Viagem ao Centro da Terra",
            ficha_unica_entre_niveis: true,
            tentativas_por_rodada: 2,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}") {
        return { data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 }, error: undefined } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return {
          data: {
            itens: [{ id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [{ id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true }],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas") {
        return {
          data: {
            itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas/{ficha_id}") {
        return { data: FICHA_COMPLETA, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });
    vi.mocked(api.POST).mockImplementation(async (path: string) => {
      if (path === "/api/v1/fichas/{ficha_id}/simular") {
        return { data: { total: 10 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            id: "lanc-1",
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            tentativa: 2,
            revision: 1,
            status: "PENDENTE",
            total: 10,
            itens: [],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/equipe/i), "eq-1");
    await screen.findByText("Lombada");
    await userEvent.selectOptions(await screen.findByLabelText(/tentativa/i), "2");
    await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
    await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ tentativa: 2 }),
        }),
      ),
    );
  });

  it("nao lista equipe que ja tem lancamento nessa rodada e tentativa", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            itens: [
              {
                id: "lanc-existente",
                equipe_id: "eq-1",
                tentativa: 1,
                status: "CONFIRMADO",
              },
            ],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}") {
        return { data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 }, error: undefined } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: { id: "mod-1", nome: "Sumo", ficha_unica_entre_niveis: true, tentativas_por_rodada: 1 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return {
          data: {
            itens: [
              { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
              { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
            ],
            total: 2,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe Y", nivel: 3, ativo: true },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas") {
        return {
          data: {
            itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    const select = await screen.findByLabelText(/equipe/i);
    await waitFor(() => {
      expect(within(select).queryByText(/Equipe X/)).not.toBeInTheDocument();
    });
    expect(within(select).getByText(/Equipe Y/)).toBeInTheDocument();
  });

  it("filtra as equipes por nivel", async () => {
    mockGet();

    renderPage();

    const selectNivel = await screen.findByLabelText(/nivel/i);
    await userEvent.selectOptions(selectNivel, "3");

    const selectEquipe = screen.getByLabelText(/^equipe$/i);
    expect(within(selectEquipe).queryByText(/Equipe X/)).not.toBeInTheDocument();
    expect(within(selectEquipe).getByText(/Equipe Y/)).toBeInTheDocument();
  });

  it("depois de confirmar, reseta o formulario e a equipe some da lista sem precisar recarregar", async () => {
    let lancamentoJaExiste = false;
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            itens: lancamentoJaExiste
              ? [{ id: "lanc-1", equipe_id: "eq-1", tentativa: 1, status: "CONFIRMADO" }]
              : [],
            total: lancamentoJaExiste ? 1 : 0,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}") {
        return { data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 }, error: undefined } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: { id: "mod-1", nome: "Sumo", ficha_unica_entre_niveis: true, tentativas_por_rodada: 1 },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return {
          data: {
            itens: [
              { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
              { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
            ],
            total: 2,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe Y", nivel: 3, ativo: true },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas") {
        return {
          data: {
            itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas/{ficha_id}") {
        return { data: FICHA_COMPLETA, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });
    vi.mocked(api.POST).mockImplementation(async (path: string) => {
      if (path === "/api/v1/fichas/{ficha_id}/simular") {
        return { data: { total: 10 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            id: "lanc-1",
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            tentativa: 1,
            revision: 1,
            status: "PENDENTE",
            total: 10,
            itens: [],
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
        lancamentoJaExiste = true;
        return {
          data: {
            id: "lanc-1",
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            tentativa: 1,
            revision: 1,
            status: "CONFIRMADO",
            total: 10,
            itens: [],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/^equipe$/i), "eq-1");
    await screen.findByText("Lombada");
    await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
    await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));
    await screen.findByText(/total persistido/i);
    await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

    await waitFor(() => {
      const select = screen.getByLabelText(/^equipe$/i) as HTMLSelectElement;
      expect(select.value).toBe("");
    });
    const select = screen.getByLabelText(/^equipe$/i);
    await waitFor(() => {
      expect(within(select).queryByText(/Equipe X/)).not.toBeInTheDocument();
    });
  });

  function mockGetConfronto(partidas: unknown[]) {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/rodadas/{rodada_id}") {
        return { data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 }, error: undefined } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: {
            id: "mod-1",
            nome: "Sumo",
            tipo_disputa: "CONFRONTO",
            ficha_unica_entre_niveis: true,
            tentativas_por_rodada: 1,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return { data: partidas, error: undefined } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return {
          data: {
            itens: [
              { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
              { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
            ],
            total: 2,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe Y", nivel: 1, ativo: true },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas") {
        return {
          data: {
            itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas/{ficha_id}") {
        return { data: FICHA_COMPLETA, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos") {
        return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
      }
      return { data: undefined, error: undefined } as never;
    });
  }

  it("para modalidade CONFRONTO, mostra seletor de partida e so as partidas em aberto", async () => {
    mockGetConfronto([
      {
        id: "partida-1",
        rodada_id: "rod-1",
        equipe_a_id: "eq-1",
        equipe_b_id: "eq-2",
        vencedor_id: null,
        status: "AGENDADA",
      },
      {
        id: "partida-2",
        rodada_id: "rod-1",
        equipe_a_id: "eq-1",
        equipe_b_id: "eq-2",
        vencedor_id: "eq-1",
        status: "ENCERRADA",
      },
    ]);

    renderPage();

    const selectPartida = await screen.findByLabelText(/partida/i);
    expect(within(selectPartida).getByText(/Equipe X.*Equipe Y/)).toBeInTheDocument();
    expect(within(selectPartida).queryAllByRole("option")).toHaveLength(2); // placeholder + 1 aberta
    expect(screen.queryByLabelText(/^equipe$/i)).not.toBeInTheDocument();
  });

  it("escolhendo a partida, deixa escolher o lado e mostra os criterios da ficha", async () => {
    mockGetConfronto([
      {
        id: "partida-1",
        rodada_id: "rod-1",
        equipe_a_id: "eq-1",
        equipe_b_id: "eq-2",
        vencedor_id: null,
        status: "AGENDADA",
      },
    ]);

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/partida/i), "partida-1");
    const selectLado = await screen.findByLabelText(/^equipe$/i);
    await userEvent.selectOptions(selectLado, "eq-1");

    expect(await screen.findByText("Lombada")).toBeInTheDocument();
  });

  it("envia partida_id no lancamento quando a modalidade e confronto", async () => {
    mockGetConfronto([
      {
        id: "partida-1",
        rodada_id: "rod-1",
        equipe_a_id: "eq-1",
        equipe_b_id: "eq-2",
        vencedor_id: null,
        status: "AGENDADA",
      },
    ]);
    vi.mocked(api.POST).mockImplementation(async (path: string) => {
      if (path === "/api/v1/fichas/{ficha_id}/simular") {
        return { data: { total: 10 }, error: undefined } as never;
      }
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            id: "lanc-1",
            ficha_id: "ficha-1",
            rodada_id: "rod-1",
            equipe_id: "eq-1",
            tentativa: 1,
            revision: 1,
            status: "PENDENTE",
            total: 10,
            itens: [],
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/partida/i), "partida-1");
    await userEvent.selectOptions(await screen.findByLabelText(/^equipe$/i), "eq-1");
    await screen.findByText("Lombada");
    await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
    await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));

    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/v1/lancamentos",
        expect.objectContaining({
          body: expect.objectContaining({ partida_id: "partida-1", equipe_id: "eq-1" }),
        }),
      ),
    );
  });

  it("lado que ja lancou nessa tentativa nao aparece no seletor da partida", async () => {
    vi.mocked(api.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/lancamentos") {
        return {
          data: {
            itens: [{ id: "l1", equipe_id: "eq-1", tentativa: 1, status: "CONFIRMADO" }],
            total: 1,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}") {
        return { data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 }, error: undefined } as never;
      }
      if (path === "/api/v1/modalidades/{modalidade_id}") {
        return {
          data: {
            id: "mod-1",
            nome: "Sumo",
            tipo_disputa: "CONFRONTO",
            ficha_unica_entre_niveis: true,
            tentativas_por_rodada: 1,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/rodadas/{rodada_id}/partidas") {
        return {
          data: [
            {
              id: "partida-1",
              rodada_id: "rod-1",
              equipe_a_id: "eq-1",
              equipe_b_id: "eq-2",
              vencedor_id: null,
              status: "AGENDADA",
            },
          ],
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/inscricoes") {
        return {
          data: {
            itens: [
              { id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" },
              { id: "ins-2", equipe_id: "eq-2", modalidade_id: "mod-1" },
            ],
            total: 2,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/equipes") {
        return {
          data: {
            itens: [
              { id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true },
              { id: "eq-2", nome: "Equipe Y", nivel: 1, ativo: true },
            ],
            total: 2,
            page: 1,
            size: 200,
          },
          error: undefined,
        } as never;
      }
      if (path === "/api/v1/fichas") {
        return {
          data: {
            itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
            total: 1,
            page: 1,
            size: 100,
          },
          error: undefined,
        } as never;
      }
      return { data: undefined, error: undefined } as never;
    });

    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText(/partida/i), "partida-1");
    const selectLado = await screen.findByLabelText(/^equipe$/i);
    expect(within(selectLado).queryByText(/Equipe X/)).not.toBeInTheDocument();
    expect(within(selectLado).getByText(/Equipe Y/)).toBeInTheDocument();
  });

  describe("vindo de um card da tela de Pontuar (equipeId na url)", () => {
    it("pula direto pra ficha, sem mostrar filtro de nivel nem seletor de equipe", async () => {
      mockGet();

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1",
      );

      expect(await screen.findByText("Lombada")).toBeInTheDocument();
      expect(screen.queryByLabelText(/^equipe$/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/filtrar por nivel/i)).not.toBeInTheDocument();
      expect(screen.getByText(/equipe x/i)).toBeInTheDocument();
    });

    it("o link de voltar aponta pra tela de Pontuar, nao pra lista de rodadas", async () => {
      mockGet();

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1",
      );

      await screen.findByText("Lombada");
      expect(screen.getByRole("link", { name: /voltar/i })).toHaveAttribute(
        "href",
        "/eventos/evt-1/modalidades/mod-1/pontuar",
      );
    });

    it("usa a tentativa vinda da url e nao mostra o seletor de tentativa", async () => {
      vi.mocked(api.GET).mockImplementation(async (path: string) => {
        if (path === "/api/v1/modalidades/{modalidade_id}") {
          return {
            data: {
              id: "mod-1",
              nome: "Viagem ao Centro da Terra",
              ficha_unica_entre_niveis: true,
              tentativas_por_rodada: 2,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/rodadas/{rodada_id}") {
          return { data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 }, error: undefined } as never;
        }
        if (path === "/api/v1/inscricoes") {
          return {
            data: {
              itens: [{ id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" }],
              total: 1,
              page: 1,
              size: 100,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/equipes") {
          return {
            data: {
              itens: [{ id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true }],
              total: 1,
              page: 1,
              size: 200,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/fichas") {
          return {
            data: {
              itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
              total: 1,
              page: 1,
              size: 100,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/fichas/{ficha_id}") {
          return { data: FICHA_COMPLETA, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return { data: { itens: [], total: 0, page: 1, size: 200 }, error: undefined } as never;
        }
        return { data: undefined, error: undefined } as never;
      });
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 2,
              revision: 1,
              status: "PENDENTE",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=2",
      );

      await screen.findByText("Lombada");
      expect(screen.queryByLabelText(/tentativa/i)).not.toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));

      await waitFor(() =>
        expect(api.POST).toHaveBeenCalledWith(
          "/api/v1/lancamentos",
          expect.objectContaining({ body: expect.objectContaining({ tentativa: 2, equipe_id: "eq-1" }) }),
        ),
      );
    });

    it("se ja existe um lancamento PENDENTE pra essa equipe+tentativa (voltou sem confirmar e reabriu o card), retoma direto pra confirmacao sem tentar recriar", async () => {
      vi.mocked(api.GET).mockImplementation(async (path: string) => {
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              itens: [
                { id: "lanc-pendente-1", equipe_id: "eq-1", tentativa: 1, status: "PENDENTE", total: 10 },
              ],
              total: 1,
              page: 1,
              size: 200,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/rodadas/{rodada_id}") {
          return { data: { id: "rod-1", modalidade_id: "mod-1", numero: 1 }, error: undefined } as never;
        }
        if (path === "/api/v1/modalidades/{modalidade_id}") {
          return {
            data: { id: "mod-1", nome: "Sumo", ficha_unica_entre_niveis: true, tentativas_por_rodada: 1 },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/inscricoes") {
          return {
            data: {
              itens: [{ id: "ins-1", equipe_id: "eq-1", modalidade_id: "mod-1" }],
              total: 1,
              page: 1,
              size: 100,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/equipes") {
          return {
            data: {
              itens: [{ id: "eq-1", nome: "Equipe X", nivel: 1, ativo: true }],
              total: 1,
              page: 1,
              size: 200,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/fichas") {
          return {
            data: {
              itens: [{ id: "ficha-1", nivel: null, versao: 1, status: "PUBLICADA" }],
              total: 1,
              page: 1,
              size: 100,
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/fichas/{ficha_id}") {
          return { data: FICHA_COMPLETA, error: undefined } as never;
        }
        return { data: undefined, error: undefined } as never;
      });
      vi.mocked(api.POST).mockImplementation(async (path: string, opts?: unknown) => {
        if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
          return {
            data: {
              id: (opts as { params: { path: { lancamento_id: string } } }).params.path.lancamento_id,
              status: "CONFIRMADO",
              total: 10,
            },
            error: undefined,
          } as never;
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1",
      );

      const blocoTotal = (await screen.findByText(/total persistido/i)).closest("div")!;
      expect(within(blocoTotal).getByText("10")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /registrar lancamento/i })).not.toBeInTheDocument();
      expect(api.POST).not.toHaveBeenCalledWith("/api/v1/lancamentos", expect.anything());

      await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

      await waitFor(() =>
        expect(api.POST).toHaveBeenCalledWith(
          "/api/v1/lancamentos/{lancamento_id}/confirmar",
          expect.objectContaining({ params: { path: { lancamento_id: "lanc-pendente-1" } } }),
        ),
      );
      expect(api.POST).not.toHaveBeenCalledWith("/api/v1/lancamentos", expect.anything());
    });

    it("depois de confirmar, volta pra tela de Pontuar da modalidade", async () => {
      mockGet();
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "PENDENTE",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "CONFIRMADO",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1",
      );

      await screen.findByText("Lombada");
      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));
      await screen.findByText(/total persistido/i);
      await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

      expect(await screen.findByText("TELA DE PONTUAR")).toBeInTheDocument();
    });

    it("preserva o filtro de nivel (?nivel=) da url ao voltar pra tela de Pontuar", async () => {
      mockGet();
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "PENDENTE",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "CONFIRMADO",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?equipeId=eq-1&tentativa=1&nivel=2",
      );

      await screen.findByText("Lombada");
      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));
      await screen.findByText(/total persistido/i);
      await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

      expect(await screen.findByText("TELA DE PONTUAR?nivel=2")).toBeInTheDocument();
    });
  });

  describe("vindo de um card de partida da tela de Pontuar de combate (partidaId na url)", () => {
    it("pula o seletor de partida e mostra a partida escolhida como texto fixo", async () => {
      mockGetConfronto([
        {
          id: "partida-1",
          rodada_id: "rod-1",
          equipe_a_id: "eq-1",
          equipe_b_id: "eq-2",
          vencedor_id: null,
          status: "AGENDADA",
        },
      ]);

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?partidaId=partida-1",
      );

      expect(await screen.findByText(/equipe x.*equipe y/i)).toBeInTheDocument();
      expect(screen.queryByLabelText(/^partida$/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText(/^equipe$/i)).toBeInTheDocument();
    });

    it("envia o partida_id vindo da url no lancamento", async () => {
      mockGetConfronto([
        {
          id: "partida-1",
          rodada_id: "rod-1",
          equipe_a_id: "eq-1",
          equipe_b_id: "eq-2",
          vencedor_id: null,
          status: "AGENDADA",
        },
      ]);
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "PENDENTE",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?partidaId=partida-1",
      );

      await userEvent.selectOptions(await screen.findByLabelText(/^equipe$/i), "eq-1");
      await screen.findByText("Lombada");
      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));

      await waitFor(() =>
        expect(api.POST).toHaveBeenCalledWith(
          "/api/v1/lancamentos",
          expect.objectContaining({
            body: expect.objectContaining({ partida_id: "partida-1", equipe_id: "eq-1" }),
          }),
        ),
      );
    });

    it("depois de confirmar, volta pra tela de Pontuar", async () => {
      mockGetConfronto([
        {
          id: "partida-1",
          rodada_id: "rod-1",
          equipe_a_id: "eq-1",
          equipe_b_id: "eq-2",
          vencedor_id: null,
          status: "AGENDADA",
        },
      ]);
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "PENDENTE",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "CONFIRMADO",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage(
        "/eventos/evt-1/modalidades/mod-1/rodadas/rod-1/lancamentos/novo?partidaId=partida-1",
      );

      await userEvent.selectOptions(await screen.findByLabelText(/^equipe$/i), "eq-1");
      await screen.findByText("Lombada");
      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));
      await screen.findByText(/total persistido/i);
      await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

      expect(await screen.findByText("TELA DE PONTUAR")).toBeInTheDocument();
    });
  });

  describe("feedback visual de fila offline (BUG-01 do relatorio de testes)", () => {
    it("registrar nao trava esperando a rede: mostra o lancamento na fila mesmo que o POST nunca responda", async () => {
      // Reproduz o BUG-01: antes, um POST que nunca resolve deixava o botao
      // preso em "Enviando..." pra sempre e nada era salvo. Agora o clique
      // so grava na fila local (Dexie) e nao espera rede nenhuma - por isso
      // nem precisa resolver o mock pra este teste passar.
      mockGet();
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return new Promise(() => {}) as never; // nunca resolve: simula rede/API fora do ar
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage();

      await userEvent.selectOptions(await screen.findByLabelText(/^equipe$/i), "eq-1");
      await screen.findByText("Lombada");
      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));

      const blocoTotal = (await screen.findByText(/total persistido/i)).closest("div")!;
      expect(within(blocoTotal).getByText("10")).toBeInTheDocument();
      expect(within(blocoTotal).getByText(/na fila/i)).toBeInTheDocument();
      // O botao "Registrar lancamento" nao pode ficar preso desabilitado -
      // ele simplesmente some, porque ja existe um lancamento ativo (na
      // fila) pra essa equipe/tentativa.
      expect(
        screen.queryByRole("button", { name: /registrar lancamento/i }),
      ).not.toBeInTheDocument();

      // Espera a chamada de fato acontecer (mesmo sem resolver) antes do
      // teste terminar, pra ela nao ficar "pendurada" e vazar sua contagem
      // de chamada pro proximo teste (timing real entre testes).
      await waitFor(() =>
        expect(api.POST).toHaveBeenCalledWith(
          "/api/v1/lancamentos",
          expect.objectContaining({ body: expect.objectContaining({ equipe_id: "eq-1" }) }),
        ),
      );
    });

    it("confirmar tambem nao espera a rede: reseta o formulario mesmo que o POST de confirmar nunca responda", async () => {
      mockGet();
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "PENDENTE",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
          return new Promise(() => {}) as never; // nunca resolve
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage();

      await userEvent.selectOptions(await screen.findByLabelText(/^equipe$/i), "eq-1");
      await screen.findByText("Lombada");
      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));
      await screen.findByText(/total persistido/i);
      await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

      await waitFor(() => {
        const select = screen.getByLabelText(/^equipe$/i) as HTMLSelectElement;
        expect(select.value).toBe("");
      });

      // Espera a chamada de confirmar de fato acontecer (mesmo sem resolver)
      // antes do teste terminar, pra ela nao ficar "pendurada" e vazar sua
      // contagem de chamada pro proximo teste (timing real entre testes).
      await waitFor(() =>
        expect(api.POST).toHaveBeenCalledWith(
          "/api/v1/lancamentos/{lancamento_id}/confirmar",
          expect.anything(),
        ),
      );
    });

    it("guarda o erro na fila local (sem repetir sozinho) quando o servidor recusa a confirmacao, mesmo com a tela ja tendo seguido em frente", async () => {
      mockGet();
      vi.mocked(api.POST).mockImplementation(async (path: string) => {
        if (path === "/api/v1/fichas/{ficha_id}/simular") {
          return { data: { total: 10 }, error: undefined } as never;
        }
        if (path === "/api/v1/lancamentos") {
          return {
            data: {
              id: "lanc-1",
              ficha_id: "ficha-1",
              rodada_id: "rod-1",
              equipe_id: "eq-1",
              tentativa: 1,
              revision: 1,
              status: "PENDENTE",
              total: 10,
              itens: [],
            },
            error: undefined,
          } as never;
        }
        if (path === "/api/v1/lancamentos/{lancamento_id}/confirmar") {
          return {
            data: undefined,
            error: { erro: { codigo: "LANCAMENTO_NAO_PENDENTE", mensagem: "Nao esta pendente." } },
            response: { status: 422 },
          } as never;
        }
        return { data: undefined, error: undefined } as never;
      });

      renderPage();

      await userEvent.selectOptions(await screen.findByLabelText(/^equipe$/i), "eq-1");
      await screen.findByText("Lombada");
      await userEvent.click(screen.getByRole("button", { name: /aumentar lombada/i }));
      await userEvent.click(screen.getByRole("button", { name: /registrar lancamento/i }));
      await screen.findByText(/total persistido/i);
      await userEvent.click(screen.getByRole("button", { name: /confirmar lancamento/i }));

      // A tela ja segue otimista pro proximo lancamento (contrato "a UI
      // confirma na hora" - secao 8 do CLAUDE.md), mas o erro nao pode ser
      // perdido: fica guardado na fila local, visivel de novo se o arbitro
      // reabrir esse mesmo lancamento (equipe+rodada+tentativa) depois.
      await waitFor(() => {
        const select = screen.getByLabelText(/^equipe$/i) as HTMLSelectElement;
        expect(select.value).toBe("");
      });

      await waitFor(async () => {
        const todos = await db.lancamentoOutbox.toArray();
        const itensConfirmar = todos.filter((item) => item.tipo === "CONFIRMAR");
        expect(itensConfirmar).toHaveLength(1);
        expect(itensConfirmar[0].status).toBe("ERRO");
      });

      const chamadasDeConfirmar = vi
        .mocked(api.POST)
        .mock.calls.filter(
          (chamada) => chamada[0] === "/api/v1/lancamentos/{lancamento_id}/confirmar",
        );
      expect(chamadasDeConfirmar).toHaveLength(1);
    });
  });
});
