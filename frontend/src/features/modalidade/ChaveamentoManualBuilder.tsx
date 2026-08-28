import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, extrairErro } from "../../api/client";
import { rotuloNivel } from "../../lib/nivel";

const BYE = "__BYE__";

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
}

interface InscricaoItem {
  equipe_id: string;
  modalidade_id: string;
}

interface RodadaItem {
  id: string;
  numero: number;
}

interface PartidaItem {
  id: string;
  equipe_a_id: string;
  equipe_b_id: string | null;
  nivel: number | null;
  formato_chaveamento?: string;
}

export function ChaveamentoManualBuilder({
  modalidadeId,
  onFechar,
}: {
  modalidadeId: string;
  onFechar: () => void;
}) {
  const queryClient = useQueryClient();
  const [nivelSelecionado, setNivelSelecionado] = useState<number | "">("");
  const [equipeAId, setEquipeAId] = useState("");
  const [equipeBId, setEquipeBId] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const { data: equipes } = useQuery({
    queryKey: ["equipes", "chaveamento-manual-builder"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  const { data: inscricoes } = useQuery({
    queryKey: ["inscricoes", "chaveamento-manual-builder", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/inscricoes", {
        params: { query: { modalidade_id: modalidadeId, size: 1000 } },
      });
      return (data?.itens ?? []) as InscricaoItem[];
    },
  });

  const { data: rodadas } = useQuery({
    queryKey: ["rodadas", "chaveamento-manual-builder", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas", {
        params: { query: { modalidade_id: modalidadeId, size: 200 } },
      });
      return (data?.itens ?? []) as RodadaItem[];
    },
  });
  const rodadasOrdenadas = [...(rodadas ?? [])].sort((a, b) => a.numero - b.numero);

  // Busca partidas de TODAS as rodadas (nao so a 1) -- precisa saber ate
  // onde o nivel ja chegou (fase de grupos + mata-mata) pra calcular a
  // rodada-alvo certa, igual o backend faz em criar_partida_manual.
  const partidasQueries = useQueries({
    queries: rodadasOrdenadas.map((rodada) => ({
      queryKey: ["partidas", "chaveamento-manual-builder", rodada.id],
      queryFn: async () => {
        const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
          params: { path: { rodada_id: rodada.id } },
        });
        return (data ?? []) as PartidaItem[];
      },
    })),
  });
  const todasPartidas = partidasQueries.flatMap((q, i) =>
    (q.data ?? []).map((p) => ({ ...p, numero: rodadasOrdenadas[i].numero })),
  );

  const equipePorId = new Map((equipes ?? []).map((e) => [e.id, e]));
  const idsInscritos = new Set((inscricoes ?? []).map((i) => i.equipe_id));
  const equipesDaModalidade = (equipes ?? []).filter((e) => idsInscritos.has(e.id));
  const niveis = Array.from(new Set(equipesDaModalidade.map((e) => e.nivel))).sort(
    (a, b) => a - b,
  );
  const nivelAtivo = nivelSelecionado === "" ? niveis[0] : nivelSelecionado;

  // Mesma regra de calculo de rodada-alvo do backend (criar_partida_manual):
  // proxima rodada apos a ultima que esse nivel ja tem partida, MAS so
  // avanca quando essa ultima foi fase de grupos (TODOS_CONTRA_TODOS) -- se
  // ja for mata-mata (outra chamada manual ainda montando a mesma rodada),
  // reaproveita o mesmo numero.
  const partidasDoNivelTodas = todasPartidas.filter((p) => p.nivel === nivelAtivo);
  const maiorNumero =
    partidasDoNivelTodas.length > 0 ? Math.max(...partidasDoNivelTodas.map((p) => p.numero)) : null;
  let numeroAlvo = 1;
  if (maiorNumero != null) {
    const naUltima = partidasDoNivelTodas.filter((p) => p.numero === maiorNumero);
    const ultimaEhMataMata = naUltima.some((p) => p.formato_chaveamento === "MATA_MATA");
    numeroAlvo = ultimaEhMataMata ? maiorNumero : maiorNumero + 1;
  }

  const idsComPartida = new Set(
    todasPartidas
      .filter((p) => p.numero === numeroAlvo)
      .flatMap((p) => [p.equipe_a_id, p.equipe_b_id].filter((x): x is string => !!x)),
  );
  const equipesDoNivel = equipesDaModalidade.filter((e) => e.nivel === nivelAtivo);
  const elegiveis = equipesDoNivel.filter((e) => !idsComPartida.has(e.id));
  const partidasDoNivel = todasPartidas.filter(
    (p) => p.nivel === nivelAtivo && p.numero === numeroAlvo,
  );

  async function invalidar() {
    await queryClient.invalidateQueries({ queryKey: ["rodadas", "chaveamento-manual-builder"] });
    await queryClient.invalidateQueries({ queryKey: ["partidas", "chaveamento-manual-builder"] });
  }

  async function salvar() {
    if (!equipeAId || !equipeBId) return;
    setEnviando(true);
    setErro(null);
    const { error } = await api.POST(
      "/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
      {
        params: { path: { modalidade_id: modalidadeId } },
        body: { equipe_a_id: equipeAId, equipe_b_id: equipeBId === BYE ? null : equipeBId },
      },
    );
    setEnviando(false);

    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    setEquipeAId("");
    setEquipeBId("");
    await invalidar();
  }

  return (
    <div
      role="dialog"
      aria-label="Montar chaveamento manual"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-1 text-lg font-semibold text-slate-800">Montar chaveamento manual</h2>
        <p className="mb-4 text-sm text-slate-500">
          Escolha as duas equipes de um confronto e salve — o confronto já vira um card pro
          árbitro pontuar. Repita um por um até fechar o nível.
        </p>

        {niveis.length > 1 && (
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nivel-manual">
              Nível
            </label>
            <select
              id="nivel-manual"
              value={nivelAtivo}
              onChange={(e) => {
                setNivelSelecionado(Number(e.target.value));
                setEquipeAId("");
                setEquipeBId("");
              }}
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

        <div className="mb-4 flex gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="equipe-a-manual">
              Equipe A
            </label>
            <select
              id="equipe-a-manual"
              value={equipeAId}
              onChange={(e) => setEquipeAId(e.target.value)}
              className="w-full rounded border border-slate-300 px-3 py-2"
            >
              <option value="">Selecione</option>
              {elegiveis.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="equipe-b-manual">
              Equipe B
            </label>
            <select
              id="equipe-b-manual"
              value={equipeBId}
              onChange={(e) => setEquipeBId(e.target.value)}
              className="w-full rounded border border-slate-300 px-3 py-2"
            >
              <option value="">Selecione</option>
              <option value={BYE}>— Bye (sem adversário) —</option>
              {elegiveis
                .filter((e) => e.id !== equipeAId)
                .map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.nome}
                  </option>
                ))}
            </select>
          </div>
        </div>

        {erro && <p className="mb-4 text-sm text-red-600">{erro}</p>}

        <button
          type="button"
          onClick={salvar}
          disabled={enviando || !equipeAId || !equipeBId}
          className="mb-6 rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {enviando ? "Salvando..." : "Salvar confronto"}
        </button>

        <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-slate-500">
          Confrontos já montados neste nível
        </h3>
        <ul className="mb-4 space-y-1">
          {partidasDoNivel.map((p) => (
            <li key={p.id} className="rounded border border-slate-200 px-3 py-1.5 text-sm">
              {equipePorId.get(p.equipe_a_id)?.nome ?? "?"} x{" "}
              {p.equipe_b_id ? (equipePorId.get(p.equipe_b_id)?.nome ?? "?") : "(bye)"}
            </li>
          ))}
          {partidasDoNivel.length === 0 && (
            <p className="text-sm text-slate-500">Nenhum confronto salvo ainda.</p>
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
