import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";

interface ModalidadeInfo {
  id: string;
  nome: string;
  tentativas_por_rodada: number;
}

interface RodadaItem {
  id: string;
  numero: number;
}

interface InscricaoItem {
  equipe_id: string;
}

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
}

interface LancamentoResumo {
  equipe_id: string;
  tentativa: number;
  status: string;
}

interface ArenaItem {
  id: string;
  nome: string;
}

interface AgendamentoItem {
  rodada_id: string;
  equipe_id: string;
  arena_id: string;
  horario_inicio: string;
}

interface Pendencia {
  equipe: EquipeItem;
  rodada: RodadaItem;
  tentativa: number;
}

function formatarHorario(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Fortaleza",
    dateStyle: "short",
    timeStyle: "short",
  });
}

export function PontuarPage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId: string }>();

  const { data: modalidade } = useQuery({
    queryKey: ["modalidade", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}", {
        params: { path: { modalidade_id: modalidadeId! } },
      });
      return data as ModalidadeInfo | undefined;
    },
    enabled: !!modalidadeId,
  });

  const { data: rodadas } = useQuery({
    queryKey: ["rodadas", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas", {
        params: { query: { modalidade_id: modalidadeId, size: 200 } },
      });
      return (data?.itens ?? []) as RodadaItem[];
    },
    enabled: !!modalidadeId,
  });
  const rodadasOrdenadas = [...(rodadas ?? [])].sort((a, b) => a.numero - b.numero);

  const { data: inscricoes } = useQuery({
    queryKey: ["inscricoes", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/inscricoes", {
        params: { query: { modalidade_id: modalidadeId, size: 200 } },
      });
      return (data?.itens ?? []) as InscricaoItem[];
    },
    enabled: !!modalidadeId,
  });

  const { data: equipesTodas } = useQuery({
    queryKey: ["equipes", "para-pontuar"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 200 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  const [nivelFiltro, setNivelFiltro] = useState("");

  const idsInscritos = new Set((inscricoes ?? []).map((i) => i.equipe_id));
  const equipesInscritas = (equipesTodas ?? []).filter((e) => idsInscritos.has(e.id));
  const niveisDisponiveis = Array.from(new Set(equipesInscritas.map((e) => e.nivel))).sort(
    (a, b) => a - b,
  );
  const equipesFiltradas = equipesInscritas.filter(
    (e) => nivelFiltro === "" || e.nivel === Number(nivelFiltro),
  );

  const lancamentosQueries = useQueries({
    queries: rodadasOrdenadas.map((rodada) => ({
      queryKey: ["lancamentos-da-rodada", rodada.id],
      queryFn: async () => {
        const { data } = await api.GET("/api/v1/lancamentos", {
          params: { query: { rodada_id: rodada.id, size: 200 } },
        });
        return (data?.itens ?? []) as LancamentoResumo[];
      },
    })),
  });
  const lancamentosPorRodada = new Map<string, LancamentoResumo[]>(
    rodadasOrdenadas.map((rodada, i) => [rodada.id, lancamentosQueries[i]?.data ?? []]),
  );

  function temLancamentoPendente(equipeId: string): boolean {
    return rodadasOrdenadas.some((rodada) =>
      (lancamentosPorRodada.get(rodada.id) ?? []).some(
        (l) => l.equipe_id === equipeId && l.status === "PENDENTE",
      ),
    );
  }

  const { data: arenas } = useQuery({
    queryKey: ["arenas", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/arenas", {
        params: { query: { modalidade_id: modalidadeId, size: 200 } },
      });
      return (data?.itens ?? []) as ArenaItem[];
    },
    enabled: !!modalidadeId,
  });
  const arenaPorId = new Map((arenas ?? []).map((a) => [a.id, a.nome]));

  const { data: agendamentos } = useQuery({
    queryKey: ["agendamentos", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/agendamentos", {
        params: { query: { modalidade_id: modalidadeId, size: 200 } },
      });
      return (data?.itens ?? []) as AgendamentoItem[];
    },
    enabled: !!modalidadeId,
  });
  const agendamentoPorRodadaEquipe = new Map(
    (agendamentos ?? []).map((a) => [`${a.rodada_id}:${a.equipe_id}`, a]),
  );

  const tentativasPorRodada = modalidade?.tentativas_por_rodada ?? 1;

  function proximaPendencia(equipeId: string): { rodada: RodadaItem; tentativa: number } | null {
    for (const rodada of rodadasOrdenadas) {
      const lancamentosDaRodada = lancamentosPorRodada.get(rodada.id) ?? [];
      for (let tentativa = 1; tentativa <= tentativasPorRodada; tentativa++) {
        const jaTem = lancamentosDaRodada.some(
          (l) => l.equipe_id === equipeId && l.tentativa === tentativa,
        );
        if (!jaTem) return { rodada, tentativa };
      }
    }
    return null;
  }

  const pendencias: Pendencia[] = [];
  const completas: EquipeItem[] = [];
  for (const equipe of equipesFiltradas) {
    const pendencia = proximaPendencia(equipe.id);
    if (pendencia) {
      pendencias.push({ equipe, ...pendencia });
    } else {
      completas.push(equipe);
    }
  }

  pendencias.sort((a, b) => {
    if (a.rodada.numero !== b.rodada.numero) return a.rodada.numero - b.rodada.numero;
    if (a.tentativa !== b.tentativa) return a.tentativa - b.tentativa;
    return a.equipe.nome.localeCompare(b.equipe.nome);
  });

  const carregando =
    !modalidade || !rodadas || !inscricoes || !equipesTodas || lancamentosQueries.some((q) => q.isLoading);

  if (carregando) {
    return (
      <main className="p-8">
        <p className="animate-pulse text-slate-500">Carregando...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link
        to={`/eventos/${eventoId}/individual?aba=pontuar`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar para pontuar
      </Link>
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Pontuar {modalidade.nome}</h1>

      {niveisDisponiveis.length > 1 && (
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="filtro-nivel">
            Filtrar por nivel
          </label>
          <select
            id="filtro-nivel"
            value={nivelFiltro}
            onChange={(e) => setNivelFiltro(e.target.value)}
            className="w-full max-w-xs rounded border border-slate-300 px-3 py-2"
          >
            <option value="">Todos os niveis</option>
            {niveisDisponiveis.map((nivel) => (
              <option key={nivel} value={nivel}>
                Nivel {nivel}
              </option>
            ))}
          </select>
        </div>
      )}

      {pendencias.length === 0 && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
          {equipesFiltradas.length === 0 ? (
            <p>Nenhuma equipe pendente: a modalidade ainda nao tem equipe inscrita.</p>
          ) : (
            <p>✓ Nenhuma equipe pendente: todas ja completaram todas as rodadas.</p>
          )}
        </div>
      )}

      <ul className="grid gap-3 sm:grid-cols-2">
        {pendencias.map(({ equipe, rodada, tentativa }) => {
          const agendamento = agendamentoPorRodadaEquipe.get(`${rodada.id}:${equipe.id}`);

          const cabecalho = (
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-lg font-semibold text-slate-800">{equipe.nome}</h2>
              {temLancamentoPendente(equipe.id) && (
                <span className="whitespace-nowrap rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                  ⚠ Pendente de confirmação
                </span>
              )}
            </div>
          );
          const corpo = (
            <>
              <p className="text-sm text-slate-500">Nível {equipe.nivel}</p>
              <p className="mt-2 text-sm font-medium text-slate-700">
                Rodada {rodada.numero}
                {tentativasPorRodada > 1 ? ` · Tentativa ${tentativa}` : ""}
              </p>
            </>
          );

          if (!agendamento) {
            return (
              <li key={equipe.id}>
                <div className="rounded-lg border border-dashed border-amber-300 bg-amber-50 p-4">
                  {cabecalho}
                  {corpo}
                  <p className="mt-2 text-xs font-medium text-amber-800">
                    ⚠ Sem arena atribuída para esta rodada
                  </p>
                  <Link
                    to={`/eventos/${eventoId}/modalidades/${modalidadeId}/horarios`}
                    className="mt-1 inline-block text-xs font-medium text-amber-900 underline"
                  >
                    Gerar horário →
                  </Link>
                </div>
              </li>
            );
          }

          return (
            <li key={equipe.id}>
              <Link
                to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodada.id}/lancamentos/novo?equipeId=${equipe.id}&tentativa=${tentativa}`}
                className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-400"
              >
                {cabecalho}
                {corpo}
                <p className="mt-1 text-xs text-slate-500">
                  {arenaPorId.get(agendamento.arena_id) ?? "Arena"} ·{" "}
                  {formatarHorario(agendamento.horario_inicio)}
                </p>
              </Link>
            </li>
          );
        })}
      </ul>

      {completas.length > 0 && (
        <p className="mt-6 flex items-center gap-1 text-sm text-slate-500">
          <span className="text-emerald-600" aria-hidden="true">
            ✓
          </span>
          {completas.length} equipe{completas.length > 1 ? "s" : ""} já completa
          {completas.length > 1 ? "ram" : ""} todas as rodadas.
        </p>
      )}
    </main>
  );
}
