import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

const MODOS_HORARIO = ["MANUAL", "AUTOMATICO"] as const;

import { api, extrairErro } from "../../api/client";
import { calcularTotalRodadasPorNivel, nomeFase } from "../../lib/fase-chaveamento";

interface ModalidadeInfo {
  id: string;
  nome: string;
  qtd_rodadas: number;
  tipo_disputa?: string;
  formato_chaveamento?: string | null;
}

interface RodadaItem {
  id: string;
  modalidade_id: string;
  numero: number;
  modo_horario: (typeof MODOS_HORARIO)[number];
  horario_inicio: string | null;
  status: string;
}

interface PartidaItem {
  id: string;
  rodada_id?: string;
  equipe_a_id: string;
  equipe_b_id: string | null;
  vencedor_id: string | null;
  status: string;
  nivel?: number | null;
}

const FORMATOS_CHAVEAMENTO = ["MATA_MATA"];

function formatarHorario(iso: string | null): string {
  if (!iso) return "Sem horario definido";
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Fortaleza",
    dateStyle: "short",
    timeStyle: "short",
  });
}

function CriarRodadaForm({
  numero,
  modalidadeId,
  onCriada,
}: {
  numero: number;
  modalidadeId: string;
  onCriada: () => void;
}) {
  const [modoHorario, setModoHorario] = useState<(typeof MODOS_HORARIO)[number]>("MANUAL");
  const [horarioInicio, setHorarioInicio] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  async function salvar() {
    setErro(null);
    if (modoHorario === "MANUAL" && !horarioInicio) {
      setErro("Informe o horario de inicio (obrigatorio no modo manual).");
      return;
    }
    const { error } = await api.POST("/api/v1/rodadas", {
      body: {
        modalidade_id: modalidadeId,
        numero,
        modo_horario: modoHorario,
        horario_inicio: horarioInicio ? new Date(horarioInicio).toISOString() : null,
      },
    });

    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    onCriada();
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div>
        <label
          className="block text-xs text-slate-600"
          htmlFor={`modo-horario-${numero}`}
        >
          Modo do horario
        </label>
        <select
          id={`modo-horario-${numero}`}
          value={modoHorario}
          onChange={(e) => setModoHorario(e.target.value as (typeof MODOS_HORARIO)[number])}
          className="rounded border border-slate-300 px-2 py-1"
        >
          {MODOS_HORARIO.map((modo) => (
            <option key={modo} value={modo}>
              {modo}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-xs text-slate-600" htmlFor={`horario-inicio-${numero}`}>
          Horario de inicio
        </label>
        <input
          id={`horario-inicio-${numero}`}
          type="datetime-local"
          value={horarioInicio}
          onChange={(e) => setHorarioInicio(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1"
        />
      </div>
      <button
        type="button"
        onClick={salvar}
        className="rounded bg-slate-800 px-3 py-1 text-sm text-white"
      >
        Salvar
      </button>
      {erro && <p className="w-full text-sm text-red-600">{erro}</p>}
    </div>
  );
}

function RodadaSlot({
  numero,
  eventoId,
  modalidadeId,
  rodada,
  onMudou,
}: {
  numero: number;
  eventoId: string;
  modalidadeId: string;
  rodada: RodadaItem | undefined;
  onMudou: () => void;
}) {
  const [criando, setCriando] = useState(false);

  return (
    <li className="rounded border border-slate-200 bg-white px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="font-medium text-slate-800">Rodada {numero}</span>

        {rodada ? (
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">{formatarHorario(rodada.horario_inicio)}</span>
            <Link
              to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodada.id}/lancamentos/novo`}
              className="text-sm font-medium text-slate-700 underline"
            >
              Lancar notas
            </Link>
            <Link
              to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodada.id}/submissoes`}
              className="text-sm font-medium text-slate-700 underline"
            >
              Ver fichas enviadas
            </Link>
          </div>
        ) : !criando ? (
          <button
            type="button"
            onClick={() => setCriando(true)}
            className="rounded bg-slate-800 px-3 py-1.5 text-sm font-medium text-white"
          >
            Criar rodada
          </button>
        ) : null}
      </div>

      {criando && !rodada && (
        <div className="mt-3">
          <CriarRodadaForm
            numero={numero}
            modalidadeId={modalidadeId}
            onCriada={() => {
              setCriando(false);
              onMudou();
            }}
          />
        </div>
      )}
    </li>
  );
}

function PartidaLinha({
  partida,
  eventoId,
  modalidadeId,
  rodadaId,
  equipePorId,
  rotuloVencedor,
}: {
  partida: PartidaItem;
  eventoId: string;
  modalidadeId: string;
  rodadaId: string;
  equipePorId: Map<string, string>;
  rotuloVencedor?: string | null;
}) {
  const decidida = partida.status === "ENCERRADA" || partida.status === "EMPATADA";
  const pendente = !decidida && partida.equipe_b_id !== null;

  return (
    <li className="flex items-center justify-between text-sm">
      <span className="text-slate-700">
        {equipePorId.get(partida.equipe_a_id) ?? "?"}
        {partida.equipe_b_id ? ` vs ${equipePorId.get(partida.equipe_b_id) ?? "?"}` : " (bye)"}
      </span>
      {decidida &&
        (partida.status === "EMPATADA" ? (
          <span className="text-xs font-medium text-slate-600">Empate</span>
        ) : (
          <span className="text-xs font-medium text-emerald-700">
            {rotuloVencedor ?? `Vencedor: ${equipePorId.get(partida.vencedor_id ?? "") ?? "?"}`}
          </span>
        ))}
      {pendente && (
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodadaId}/partidas/${partida.id}/pontuar`}
          className="text-xs font-medium text-slate-700 underline"
        >
          Pontuar
        </Link>
      )}
    </li>
  );
}

function PartidasRodada({
  rodada,
  eventoId,
  modalidadeId,
  equipePorId,
}: {
  rodada: RodadaItem;
  eventoId: string;
  modalidadeId: string;
  equipePorId: Map<string, string>;
}) {
  const { data: partidas } = useQuery({
    queryKey: ["partidas-da-rodada", rodada.id],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
        params: { path: { rodada_id: rodada.id } },
      });
      return (data ?? []) as PartidaItem[];
    },
  });

  const partidasPorNivel = new Map<number | null, PartidaItem[]>();
  for (const partida of partidas ?? []) {
    const chave = partida.nivel ?? null;
    if (!partidasPorNivel.has(chave)) partidasPorNivel.set(chave, []);
    partidasPorNivel.get(chave)!.push(partida);
  }
  const niveis = [...partidasPorNivel.keys()].sort((a, b) => (a ?? 0) - (b ?? 0));

  return (
    <li className="rounded border border-slate-200 bg-white px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium text-slate-800">Rodada {rodada.numero}</span>
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodada.id}/submissoes`}
          className="text-sm font-medium text-slate-700 underline"
        >
          Ver fichas enviadas
        </Link>
      </div>
      <div className="space-y-3">
        {niveis.map((nivel) => (
          <div key={String(nivel)}>
            {nivel != null && (
              <span className="mb-1 block text-xs font-medium text-slate-500">Nível {nivel}</span>
            )}
            <ul className="space-y-1">
              {partidasPorNivel.get(nivel)!.map((partida) => (
                <PartidaLinha
                  key={partida.id}
                  partida={partida}
                  eventoId={eventoId}
                  modalidadeId={modalidadeId}
                  rodadaId={rodada.id}
                  equipePorId={equipePorId}
                />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </li>
  );
}

function BracketRodada({
  rodada,
  eventoId,
  modalidadeId,
  equipePorId,
  ultimaRodadaPorNivel,
  totalRodadasPorNivel,
}: {
  rodada: RodadaItem;
  eventoId: string;
  modalidadeId: string;
  equipePorId: Map<string, string>;
  ultimaRodadaPorNivel: Map<number, number>;
  totalRodadasPorNivel: Map<number, number>;
}) {
  const { data: partidas } = useQuery({
    queryKey: ["partidas-da-rodada", rodada.id],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
        params: { path: { rodada_id: rodada.id } },
      });
      return (data ?? []) as PartidaItem[];
    },
  });

  const partidasPorNivel = new Map<number | null, PartidaItem[]>();
  for (const partida of partidas ?? []) {
    const chave = partida.nivel ?? null;
    if (!partidasPorNivel.has(chave)) partidasPorNivel.set(chave, []);
    partidasPorNivel.get(chave)!.push(partida);
  }
  const niveis = [...partidasPorNivel.keys()].sort((a, b) => (a ?? 0) - (b ?? 0));

  return (
    <li className="rounded border border-slate-200 bg-white px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium text-slate-800">Rodada {rodada.numero}</span>
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodada.id}/submissoes`}
          className="text-sm font-medium text-slate-700 underline"
        >
          Ver fichas enviadas
        </Link>
      </div>
      <div className="space-y-3">
        {niveis.map((nivel) => {
          const fase =
            nivel != null ? nomeFase(rodada.numero, totalRodadasPorNivel.get(nivel)) : null;
          const partidasDoNivel = partidasPorNivel.get(nivel)!;
          const ehRodadaFinalDoNivel =
            nivel != null &&
            rodada.numero === ultimaRodadaPorNivel.get(nivel) &&
            partidasDoNivel.length === 1;
          return (
            <div key={String(nivel)}>
              {nivel != null && (
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-500">Nível {nivel}</span>
                  {fase && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${fase.classes}`}
                    >
                      {fase.nome}
                    </span>
                  )}
                </div>
              )}
              <ul className="space-y-1">
                {partidasDoNivel.map((partida) => {
                  const decidida = partida.status === "ENCERRADA" || partida.status === "EMPATADA";
                  const pendente = !decidida && partida.equipe_b_id !== null;
                  return (
                    <li key={partida.id} className="flex items-center justify-between text-sm">
                      <span className="text-slate-700">
                        {equipePorId.get(partida.equipe_a_id) ?? "?"}
                        {partida.equipe_b_id
                          ? ` vs ${equipePorId.get(partida.equipe_b_id) ?? "?"}`
                          : " (bye)"}
                      </span>
                      {partida.vencedor_id && (
                        <span className="text-xs font-medium text-emerald-700">
                          {ehRodadaFinalDoNivel && partida.status === "ENCERRADA"
                            ? `🏆 Campeão: ${equipePorId.get(partida.vencedor_id) ?? "?"}`
                            : `Vencedor: ${equipePorId.get(partida.vencedor_id) ?? "?"}`}
                        </span>
                      )}
                      {pendente && (
                        <Link
                          to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodada.id}/partidas/${partida.id}/pontuar`}
                          className="text-xs font-medium text-slate-700 underline"
                        >
                          Pontuar
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </li>
  );
}

export function RodadaListPage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId: string }>();
  const queryClient = useQueryClient();

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

  const isBracket =
    modalidade?.tipo_disputa === "CONFRONTO" &&
    FORMATOS_CHAVEAMENTO.includes(modalidade.formato_chaveamento ?? "");
  const isTodosContraTodos =
    modalidade?.tipo_disputa === "CONFRONTO" &&
    modalidade.formato_chaveamento === "TODOS_CONTRA_TODOS";
  const isCombate = isBracket || isTodosContraTodos;

  const { data: equipesTodas } = useQuery({
    queryKey: ["equipes", "para-bracket"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as { id: string; nome: string }[];
    },
    enabled: isCombate,
  });
  const equipePorId = new Map((equipesTodas ?? []).map((e) => [e.id, e.nome]));

  const rodadasOrdenadas = [...(rodadas ?? [])].sort((a, b) => a.numero - b.numero);
  const partidasQueries = useQueries({
    queries: isBracket
      ? rodadasOrdenadas.map((rodada) => ({
          queryKey: ["partidas-da-rodada", rodada.id],
          queryFn: async () => {
            const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
              params: { path: { rodada_id: rodada.id } },
            });
            return (data ?? []) as PartidaItem[];
          },
        }))
      : [],
  });

  // Ultima rodada em que cada nivel tem alguma partida gerada ate agora.
  // Uma partida so e a decisao do campeao se estiver nessa rodada E for a
  // UNICA partida do nivel ali - senao pode ser so a rodada mais recente
  // conhecida (ex.: semifinal com 2 jogos, um ja fechado) e nao a final de
  // verdade. Comparar so o vencedor_id com "quem e campeao" e um erro: o
  // proprio campeao tambem venceu rodadas anteriores, e aquelas partidas nao
  // podem herdar o troféu.
  const ultimaRodadaPorNivel = new Map<number, number>();
  if (isBracket) {
    const rodadaPorId = new Map(rodadasOrdenadas.map((r) => [r.id, r]));
    const todasPartidas = partidasQueries.flatMap((q) => q.data ?? []);
    for (const partida of todasPartidas) {
      if (partida.nivel == null) continue;
      const numero = rodadaPorId.get(partida.rodada_id ?? "")?.numero;
      if (numero == null) continue;
      if (numero > (ultimaRodadaPorNivel.get(partida.nivel) ?? -1)) {
        ultimaRodadaPorNivel.set(partida.nivel, numero);
      }
    }
  }

  let totalRodadasPorNivel = new Map<number, number>();
  if (isBracket) {
    const rodada1Idx = rodadasOrdenadas.findIndex((r) => r.numero === 1);
    const partidas1 = rodada1Idx >= 0 ? (partidasQueries[rodada1Idx]?.data ?? []) : [];
    totalRodadasPorNivel = calcularTotalRodadasPorNivel(
      partidas1.map((p) => ({ ...p, nivel: p.nivel ?? null })),
    );
  }

  const [erroChaveamento, setErroChaveamento] = useState<string | null>(null);

  function onMudou() {
    void queryClient.invalidateQueries({ queryKey: ["rodadas", modalidadeId] });
  }

  async function gerarRodadas() {
    await api.POST("/api/v1/rodadas/gerar", { body: { modalidade_id: modalidadeId! } });
    onMudou();
  }

  async function gerarChaveamento() {
    setErroChaveamento(null);
    const { error } = await api.POST("/api/v1/chaveamento/gerar", {
      body: { modalidade_id: modalidadeId! },
    });
    if (error) {
      setErroChaveamento(extrairErro(error).mensagem);
      return;
    }
    onMudou();
  }

  if (!modalidade || !rodadas || (isCombate && !equipesTodas)) {
    return <main className="p-8 text-slate-500">Carregando...</main>;
  }

  const numeros = Array.from({ length: modalidade.qtd_rodadas }, (_, i) => i + 1);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link
        to={`/eventos/${eventoId}/modalidades`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar para modalidades
      </Link>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-800">Rodadas de {modalidade.nome}</h1>
        {isBracket ? (
          rodadas.length === 0 && (
            <button
              type="button"
              onClick={gerarChaveamento}
              className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white"
            >
              Gerar chaveamento
            </button>
          )
        ) : (
          <button
            type="button"
            onClick={gerarRodadas}
            className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white"
          >
            Gerar rodadas
          </button>
        )}
      </div>

      {erroChaveamento && <p className="mb-4 text-sm text-red-600">{erroChaveamento}</p>}

      {isBracket ? (
        <ul className="space-y-2">
          {rodadasOrdenadas.map((rodada) => (
            <BracketRodada
              key={rodada.id}
              rodada={rodada}
              eventoId={eventoId!}
              modalidadeId={modalidadeId!}
              equipePorId={equipePorId}
              ultimaRodadaPorNivel={ultimaRodadaPorNivel}
              totalRodadasPorNivel={totalRodadasPorNivel}
            />
          ))}
        </ul>
      ) : isTodosContraTodos ? (
        <ul className="space-y-2">
          {rodadasOrdenadas.map((rodada) => (
            <PartidasRodada
              key={rodada.id}
              rodada={rodada}
              eventoId={eventoId!}
              modalidadeId={modalidadeId!}
              equipePorId={equipePorId}
            />
          ))}
        </ul>
      ) : (
        <ul className="space-y-2">
          {numeros.map((numero) => (
            <RodadaSlot
              key={numero}
              numero={numero}
              eventoId={eventoId!}
              modalidadeId={modalidadeId!}
              rodada={rodadas.find((r) => r.numero === numero)}
              onMudou={onMudou}
            />
          ))}
        </ul>
      )}
    </main>
  );
}
