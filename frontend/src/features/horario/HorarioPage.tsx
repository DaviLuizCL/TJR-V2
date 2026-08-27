import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { rotuloNivel } from "../../lib/nivel";

interface ModalidadeInfo {
  id: string;
  nome: string;
  niveis_aplicaveis: number[];
}

interface RodadaItem {
  id: string;
  numero: number;
}

interface ArenaItem {
  id: string;
  modalidade_id: string;
  nome: string;
  niveis_aplicaveis: number[] | null;
  ativo: boolean;
}

interface AgendamentoItem {
  id: string;
  rodada_id: string;
  equipe_id: string;
  arena_id: string;
  ordem_na_arena: number;
  horario_inicio: string;
}

interface EstimativaItem {
  agendamento_id: string;
  horario_previsto: string;
}

interface EquipeItem {
  id: string;
  nome: string;
}

function formatarHorario(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Fortaleza",
    dateStyle: "short",
    timeStyle: "short",
  });
}

function NovaArenaForm({
  modalidadeId,
  niveisDaModalidade,
  onCriada,
}: {
  modalidadeId: string;
  niveisDaModalidade: number[];
  onCriada: () => void;
}) {
  const [nome, setNome] = useState("");
  const [niveis, setNiveis] = useState<number[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  function alternarNivel(nivel: number) {
    setNiveis((atual) =>
      atual.includes(nivel) ? atual.filter((n) => n !== nivel) : [...atual, nivel],
    );
  }

  async function criar() {
    setErro(null);
    const { error } = await api.POST("/api/v1/arenas", {
      body: {
        modalidade_id: modalidadeId,
        nome,
        niveis_aplicaveis: niveis.length > 0 ? niveis : null,
        ativo: true,
      },
    });
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    setNome("");
    setNiveis([]);
    onCriada();
  }

  return (
    <div className="flex flex-wrap items-end gap-3 rounded border border-slate-200 bg-white p-4">
      <div>
        <label className="block text-xs text-slate-600" htmlFor="nome-arena">
          Nome da arena
        </label>
        <input
          id="nome-arena"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1"
        />
      </div>
      <div>
        <span className="block text-xs text-slate-600">Níveis (vazio = todos)</span>
        <div className="flex gap-2">
          {niveisDaModalidade.map((nivel) => (
            <label key={nivel} className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={niveis.includes(nivel)}
                onChange={() => alternarNivel(nivel)}
              />
              {rotuloNivel(nivel)}
            </label>
          ))}
        </div>
      </div>
      <button
        type="button"
        onClick={criar}
        disabled={!nome}
        className="rounded bg-slate-800 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
      >
        Criar arena
      </button>
      {erro && <p className="w-full text-sm text-red-600">{erro}</p>}
    </div>
  );
}

export function HorarioPage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId: string }>();
  const queryClient = useQueryClient();
  const usuario = useAuthStore((state) => state.usuario);
  const ehCoordenador = usuario?.papel === "COORDENADOR";

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

  const { data: estimativas } = useQuery({
    queryKey: ["agendamentos-estimativa", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/agendamentos/estimativa", {
        params: { query: { modalidade_id: modalidadeId! } },
      });
      return (data ?? []) as EstimativaItem[];
    },
    enabled: !!modalidadeId,
    refetchInterval: 30_000,
  });
  const horarioPrevistoPorAgendamento = new Map(
    (estimativas ?? []).map((e) => [e.agendamento_id, e.horario_previsto]),
  );

  const { data: equipesTodas } = useQuery({
    queryKey: ["equipes", "para-horarios"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });
  const equipePorId = new Map((equipesTodas ?? []).map((e) => [e.id, e.nome]));
  const arenaPorId = new Map((arenas ?? []).map((a) => [a.id, a.nome]));
  const rodadaPorId = new Map((rodadas ?? []).map((r) => [r.id, r.numero]));

  const [rodadasSelecionadas, setRodadasSelecionadas] = useState<string[]>([]);
  const [horarioInicio, setHorarioInicio] = useState("");
  const [erroGeracao, setErroGeracao] = useState<string | null>(null);
  const [conflito, setConflito] = useState(false);

  function alternarRodadaSelecionada(rodadaId: string) {
    setRodadasSelecionadas((atual) =>
      atual.includes(rodadaId) ? atual.filter((id) => id !== rodadaId) : [...atual, rodadaId],
    );
  }

  async function invalidar() {
    await queryClient.invalidateQueries({ queryKey: ["agendamentos", modalidadeId] });
    await queryClient.invalidateQueries({ queryKey: ["rodadas", modalidadeId] });
  }

  async function gerarHorario(regenerar = false) {
    setErroGeracao(null);
    const { error } = await api.POST("/api/v1/agendamentos/gerar", {
      body: {
        modalidade_id: modalidadeId!,
        rodada_ids: rodadasSelecionadas,
        horario_inicio: horarioInicio ? new Date(horarioInicio).toISOString() : "",
        regenerar,
      },
    });
    if (error) {
      const erro = extrairErro(error);
      setErroGeracao(erro.mensagem);
      setConflito(erro.codigo === "AGENDAMENTO_JA_EXISTE");
      return;
    }
    setConflito(false);
    await invalidar();
  }

  async function alternarAtivoArena(arena: ArenaItem) {
    await api.PATCH("/api/v1/arenas/{arena_id}", {
      params: { path: { arena_id: arena.id } },
      body: { ativo: !arena.ativo },
    });
    await queryClient.invalidateQueries({ queryKey: ["arenas", modalidadeId] });
  }

  const agendamentosPorRodada = new Map<string, AgendamentoItem[]>();
  for (const agendamento of agendamentos ?? []) {
    const lista = agendamentosPorRodada.get(agendamento.rodada_id) ?? [];
    lista.push(agendamento);
    agendamentosPorRodada.set(agendamento.rodada_id, lista);
  }

  if (!modalidade) {
    return <main className="p-8 text-slate-500">Carregando...</main>;
  }

  return (
    <main className="mx-auto max-w-4xl p-8">
      <Link
        to={`/eventos/${eventoId}/competicoes?aba=individual&sub=horarios`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar para horários
      </Link>
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Horários de {modalidade.nome}</h1>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">Arenas</h2>
        <ul className="mb-3 space-y-2">
          {arenas?.map((arena) => (
            <li
              key={arena.id}
              className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-2"
            >
              <div>
                <span className="font-medium text-slate-800">{arena.nome}</span>
                <span className="ml-2 text-sm text-slate-500">
                  {arena.niveis_aplicaveis
                    ? `Níveis ${arena.niveis_aplicaveis.map(rotuloNivel).join(", ")}`
                    : "Todos os níveis"}
                </span>
              </div>
              {ehCoordenador && (
                <button
                  type="button"
                  onClick={() => alternarAtivoArena(arena)}
                  className="text-sm font-medium text-slate-700 underline"
                >
                  {arena.ativo ? "Desativar" : "Ativar"}
                </button>
              )}
            </li>
          ))}
          {arenas?.length === 0 && <p className="text-slate-500">Nenhuma arena cadastrada.</p>}
        </ul>

        {ehCoordenador && (
          <NovaArenaForm
            modalidadeId={modalidadeId!}
            niveisDaModalidade={modalidade.niveis_aplicaveis}
            onCriada={() => queryClient.invalidateQueries({ queryKey: ["arenas", modalidadeId] })}
          />
        )}
      </section>

      {ehCoordenador && (
        <section className="mb-8 rounded border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
            Gerar horário
          </h2>
          <div className="mb-3 flex flex-wrap gap-3">
            {rodadas?.map((rodada) => (
              <label key={rodada.id} className="flex items-center gap-1 text-sm">
                <input
                  type="checkbox"
                  checked={rodadasSelecionadas.includes(rodada.id)}
                  onChange={() => alternarRodadaSelecionada(rodada.id)}
                />
                Rodada {rodada.numero}
              </label>
            ))}
          </div>
          <div className="mb-3">
            <label className="block text-xs text-slate-600" htmlFor="horario-inicio-geracao">
              Horário de início
            </label>
            <input
              id="horario-inicio-geracao"
              type="datetime-local"
              value={horarioInicio}
              onChange={(e) => setHorarioInicio(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1"
            />
          </div>
          <button
            type="button"
            onClick={() => gerarHorario(false)}
            disabled={rodadasSelecionadas.length === 0 || !horarioInicio}
            className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Gerar horário
          </button>
          {erroGeracao && (
            <div className="mt-2">
              <p className="text-sm text-red-600">{erroGeracao}</p>
              {conflito && (
                <button
                  type="button"
                  onClick={() => gerarHorario(true)}
                  className="mt-1 rounded border border-red-600 px-3 py-1 text-sm font-medium text-red-600"
                >
                  Gerar mesmo assim
                </button>
              )}
            </div>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Agenda gerada
        </h2>
        {(!agendamentos || agendamentos.length === 0) && (
          <p className="text-slate-500">Nenhum horário gerado ainda.</p>
        )}
        <div className="space-y-4">
          {[...agendamentosPorRodada.entries()]
            .sort(([a], [b]) => (rodadaPorId.get(a) ?? 0) - (rodadaPorId.get(b) ?? 0))
            .map(([rodadaId, itens]) => (
              <div key={rodadaId}>
                <p className="mb-2 font-medium text-slate-800">Rodada {rodadaPorId.get(rodadaId)}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {[...new Set(itens.map((i) => i.arena_id))].map((arenaId) => (
                    <div key={arenaId} className="rounded border border-slate-200 bg-white p-3">
                      <p className="mb-1 text-sm font-semibold text-slate-700">
                        {arenaPorId.get(arenaId) ?? "?"}
                      </p>
                      <ul className="space-y-1 text-sm">
                        {itens
                          .filter((i) => i.arena_id === arenaId)
                          .sort((a, b) => a.ordem_na_arena - b.ordem_na_arena)
                          .map((item) => (
                            <li key={item.id} className="flex items-center justify-between">
                              <span>{equipePorId.get(item.equipe_id) ?? "?"}</span>
                              <span className="text-slate-500">
                                {formatarHorario(
                                  horarioPrevistoPorAgendamento.get(item.id) ??
                                    item.horario_inicio,
                                )}
                              </span>
                            </li>
                          ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            ))}
        </div>
      </section>
    </main>
  );
}
