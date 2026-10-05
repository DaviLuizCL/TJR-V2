import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, extrairErro } from "../../api/client";
import { rotuloNivel } from "../../lib/nivel";

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
  presente?: boolean;
}

interface InscricaoItem {
  equipe_id: string;
  modalidade_id: string;
}

interface ChaveItem {
  id: string;
  modalidade_id: string;
  nivel: number;
  nome: string;
  equipe_ids: string[];
}

interface ClassificacaoChaveItem {
  equipe_id: string;
  nota_final: number;
  vitorias: number;
  empates: number;
  derrotas: number;
  posicao: number;
}

const QUERY_KEY_CHAVES = ["chaves", "fase-de-grupos-builder"];

export function FaseDeGruposBuilder({
  modalidadeId,
  onFechar,
}: {
  modalidadeId: string;
  onFechar: () => void;
}) {
  const queryClient = useQueryClient();
  const [nivelSelecionado, setNivelSelecionado] = useState<number | "">("");
  const [nomeNovaChave, setNomeNovaChave] = useState("");
  const [equipeParaAdicionar, setEquipeParaAdicionar] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const { data: equipes } = useQuery({
    queryKey: ["equipes", "fase-de-grupos-builder"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  const { data: inscricoes } = useQuery({
    queryKey: ["inscricoes", "fase-de-grupos-builder", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/inscricoes", {
        params: { query: { modalidade_id: modalidadeId, size: 1000 } },
      });
      return (data?.itens ?? []) as InscricaoItem[];
    },
  });

  const { data: chaves } = useQuery({
    queryKey: [...QUERY_KEY_CHAVES, modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}/chaves", {
        params: { path: { modalidade_id: modalidadeId } },
      });
      return (data ?? []) as ChaveItem[];
    },
  });

  const equipePorId = new Map((equipes ?? []).map((e) => [e.id, e]));
  const idsInscritos = new Set((inscricoes ?? []).map((i) => i.equipe_id));
  const equipesDaModalidade = (equipes ?? []).filter((e) => idsInscritos.has(e.id));
  const niveis = Array.from(new Set(equipesDaModalidade.map((e) => e.nivel))).sort(
    (a, b) => a - b,
  );
  const nivelAtivo = nivelSelecionado === "" ? niveis[0] : nivelSelecionado;

  const idsJaEmChave = new Set((chaves ?? []).flatMap((c) => c.equipe_ids));
  const chavesDoNivel = (chaves ?? []).filter((c) => c.nivel === nivelAtivo);
  const equipesSemChaveDoNivel = equipesDaModalidade.filter(
    (e) => e.nivel === nivelAtivo && !idsJaEmChave.has(e.id) && e.presente !== false,
  );

  // Sem isso o coordenador nao tem como saber quem ficou em 1o/2o de cada
  // chave pra decidir o mata-mata manual depois -- o endpoint ja existia,
  // so faltava aparecer em algum lugar da tela.
  const classificacaoQueries = useQueries({
    queries: chavesDoNivel.map((chave) => ({
      queryKey: ["classificacao-chave", chave.id],
      queryFn: async () => {
        const { data } = await api.GET("/api/v1/chaves/{chave_id}/classificacao", {
          params: { path: { chave_id: chave.id } },
        });
        return (data ?? []) as ClassificacaoChaveItem[];
      },
      enabled: chave.equipe_ids.length > 0,
    })),
  });
  const classificacaoPorChave = new Map(
    chavesDoNivel.map((chave, i) => [chave.id, classificacaoQueries[i]?.data ?? []]),
  );

  async function invalidar() {
    await queryClient.invalidateQueries({ queryKey: QUERY_KEY_CHAVES });
    await queryClient.invalidateQueries({ queryKey: ["classificacao-chave"] });
    await queryClient.invalidateQueries({ queryKey: ["rodadas"] });
    await queryClient.invalidateQueries({ queryKey: ["partidas-da-rodada"] });
  }

  async function criarChave() {
    if (!nomeNovaChave.trim() || nivelAtivo == null) return;
    setEnviando(true);
    setErro(null);
    const { error } = await api.POST("/api/v1/modalidades/{modalidade_id}/chaves", {
      params: { path: { modalidade_id: modalidadeId } },
      body: { modalidade_id: modalidadeId, nivel: nivelAtivo, nome: nomeNovaChave.trim() },
    });
    setEnviando(false);
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    setNomeNovaChave("");
    await invalidar();
  }

  async function adicionarEquipe(chaveId: string) {
    const equipeId = equipeParaAdicionar[chaveId];
    if (!equipeId) return;
    setErro(null);
    const { error } = await api.POST("/api/v1/chaves/{chave_id}/equipes", {
      params: { path: { chave_id: chaveId } },
      body: { equipe_id: equipeId },
    });
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    setEquipeParaAdicionar((atual) => ({ ...atual, [chaveId]: "" }));
    await invalidar();
  }

  async function removerEquipe(chaveId: string, equipeId: string) {
    setErro(null);
    const { error } = await api.DELETE("/api/v1/chaves/{chave_id}/equipes/{equipe_id}", {
      params: { path: { chave_id: chaveId, equipe_id: equipeId } },
    });
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    await invalidar();
  }

  return (
    <div
      role="dialog"
      aria-label="Montar fase de grupos"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-1 text-lg font-semibold text-slate-800">Montar fase de grupos</h2>
        <p className="mb-4 text-sm text-slate-500">
          Crie as chaves (grupos) do nível e distribua as equipes entre elas. Os confrontos são
          montados em "Montar chaveamento manual" com o tipo "Fase de grupos" — quando as duas
          equipes estão na mesma chave, o confronto entra na classificação dela.
        </p>

        {niveis.length > 1 && (
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nivel-fase-grupos">
              Nível
            </label>
            <select
              id="nivel-fase-grupos"
              value={nivelAtivo}
              onChange={(e) => setNivelSelecionado(Number(e.target.value))}
              className="w-full rounded border border-slate-300 px-3 py-2"
            >
              {niveis.map((n) => (
                <option key={n} value={n}>
                  {rotuloNivel(n)}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="mb-4 flex gap-2">
          <input
            type="text"
            value={nomeNovaChave}
            onChange={(e) => setNomeNovaChave(e.target.value)}
            placeholder="Nome da chave (ex.: Chave A)"
            aria-label="Nome da nova chave"
            className="flex-1 rounded border border-slate-300 px-3 py-2"
          />
          <button
            type="button"
            onClick={criarChave}
            disabled={enviando || !nomeNovaChave.trim()}
            className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Criar chave
          </button>
        </div>

        {erro && <p className="mb-4 text-sm text-red-600">{erro}</p>}

        <ul className="mb-6 space-y-3">
          {chavesDoNivel.map((chave) => (
            <li key={chave.id} className="rounded border border-slate-200 p-3">
              <p className="mb-2 text-sm font-semibold text-slate-800">{chave.nome}</p>
              <ul className="mb-2 space-y-1">
                {chave.equipe_ids.map((equipeId) => (
                  <li
                    key={equipeId}
                    className="flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-sm"
                  >
                    <span>{equipePorId.get(equipeId)?.nome ?? "?"}</span>
                    <button
                      type="button"
                      onClick={() => removerEquipe(chave.id, equipeId)}
                      className="text-xs font-medium text-red-600 underline"
                    >
                      Remover
                    </button>
                  </li>
                ))}
                {chave.equipe_ids.length === 0 && (
                  <li className="text-sm text-slate-500">Nenhuma equipe ainda.</li>
                )}
              </ul>

              {(classificacaoPorChave.get(chave.id)?.length ?? 0) > 0 && (
                <div className="mb-2">
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                    Classificação
                  </p>
                  <ol
                    aria-label={`Classificação da ${chave.nome}`}
                    className="space-y-0.5 text-sm text-slate-700"
                  >
                    {[...(classificacaoPorChave.get(chave.id) ?? [])]
                      .sort((a, b) => a.posicao - b.posicao)
                      .map((item) => (
                        <li key={item.equipe_id} className="flex justify-between">
                          <span>
                            {item.posicao}º {equipePorId.get(item.equipe_id)?.nome ?? "?"}
                          </span>
                          <span className="text-slate-500">
                            {item.vitorias}V {item.empates}E {item.derrotas}D · {item.nota_final}{" "}
                            pts
                          </span>
                        </li>
                      ))}
                  </ol>
                </div>
              )}

              <div className="flex gap-2">
                <select
                  aria-label={`Adicionar equipe na ${chave.nome}`}
                  value={equipeParaAdicionar[chave.id] ?? ""}
                  onChange={(e) =>
                    setEquipeParaAdicionar((atual) => ({ ...atual, [chave.id]: e.target.value }))
                  }
                  className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">Selecione uma equipe</option>
                  {equipesSemChaveDoNivel.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.nome}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => adicionarEquipe(chave.id)}
                  disabled={!equipeParaAdicionar[chave.id]}
                  className="rounded border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 disabled:opacity-50"
                >
                  Adicionar
                </button>
              </div>
            </li>
          ))}
          {chavesDoNivel.length === 0 && (
            <p className="text-sm text-slate-500">Nenhuma chave criada ainda neste nível.</p>
          )}
        </ul>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={onFechar}
            className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
