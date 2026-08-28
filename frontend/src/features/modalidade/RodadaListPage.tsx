import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

const MODOS_HORARIO = ["MANUAL", "AUTOMATICO"] as const;

import { api, extrairErro } from "../../api/client";
import {
  calcularTotalRodadasPorNivel,
  nomeFase,
  primeiraRodadaMataMataPorNivel,
} from "../../lib/fase-chaveamento";
import { rotuloNivel } from "../../lib/nivel";
import { ChaveamentoManualBuilder } from "./ChaveamentoManualBuilder";
import { FaseDeGruposBuilder } from "./FaseDeGruposBuilder";

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
  formato_chaveamento?: string;
  chave_id?: string | null;
}

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

function CombateRodada({
  rodada,
  eventoId,
  modalidadeId,
  equipePorId,
  ultimaRodadaPorNivel,
  totalRodadasPorNivel,
  inicioMataMataPorNivel,
  chavePorId,
}: {
  rodada: RodadaItem;
  eventoId: string;
  modalidadeId: string;
  equipePorId: Map<string, string>;
  ultimaRodadaPorNivel: Map<number, number>;
  totalRodadasPorNivel: Map<number, number>;
  inicioMataMataPorNivel: Map<number, number>;
  chavePorId: Map<string, string>;
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
          const partidasDoNivel = partidasPorNivel.get(nivel)!;
          // Cada nivel tem UM formato so (Partida.formato_chaveamento e
          // gravado no momento em que gerar_chaveamento_confronto decide,
          // por nivel) -- olhar a primeira partida basta.
          const ehBracket = partidasDoNivel[0]?.formato_chaveamento === "MATA_MATA";
          // numero relativo ao inicio do mata-mata daquele nivel, nao o
          // absoluto da modalidade -- depois de fase de grupos o bracket
          // pode comecar numa rodada != 1 (ver lib/fase-chaveamento.ts).
          const inicio = nivel != null ? inicioMataMataPorNivel.get(nivel) : undefined;
          const numeroRelativo = inicio != null ? rodada.numero - inicio + 1 : rodada.numero;
          const fase =
            ehBracket && nivel != null
              ? nomeFase(numeroRelativo, totalRodadasPorNivel.get(nivel))
              : null;
          const ehRodadaFinalDoNivel =
            ehBracket &&
            nivel != null &&
            rodada.numero === ultimaRodadaPorNivel.get(nivel) &&
            partidasDoNivel.length === 1;
          return (
            <div key={String(nivel)}>
              {nivel != null && (
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-500">{rotuloNivel(nivel)}</span>
                  {fase && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${fase.classes}`}
                    >
                      {fase.nome}
                    </span>
                  )}
                </div>
              )}
              {(() => {
                function partidaLinha(partida: PartidaItem) {
                  return (
                    <PartidaLinha
                      key={partida.id}
                      partida={partida}
                      eventoId={eventoId}
                      modalidadeId={modalidadeId}
                      rodadaId={rodada.id}
                      equipePorId={equipePorId}
                      rotuloVencedor={
                        ehRodadaFinalDoNivel &&
                        partida.status === "ENCERRADA" &&
                        partida.vencedor_id
                          ? `🏆 Campeão: ${equipePorId.get(partida.vencedor_id) ?? "?"}`
                          : undefined
                      }
                    />
                  );
                }

                // Partida de fase de grupos carrega chave_id -- separa em
                // sub-blocos com o nome da chave por cima, pra ficar claro
                // quem e de qual grupo (sem isso, um nivel com 5 chaves
                // virava uma lista plana de 5+ confrontos sem nenhuma
                // indicacao visual de qual e qual).
                const gruposPorChave = new Map<string, PartidaItem[]>();
                for (const partida of partidasDoNivel) {
                  const chaveKey = partida.chave_id ?? "";
                  if (!gruposPorChave.has(chaveKey)) gruposPorChave.set(chaveKey, []);
                  gruposPorChave.get(chaveKey)!.push(partida);
                }
                const temChave = [...gruposPorChave.keys()].some((k) => k !== "");

                if (!temChave) {
                  return <ul className="space-y-1">{partidasDoNivel.map(partidaLinha)}</ul>;
                }
                return (
                  <div className="space-y-2">
                    {[...gruposPorChave.entries()].map(([chaveId, lista]) => (
                      <div key={chaveId || "sem-chave"}>
                        {chaveId && (
                          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                            {chavePorId.get(chaveId) ?? "Fase de Grupos"}
                          </p>
                        )}
                        <ul className="space-y-1">{lista.map(partidaLinha)}</ul>
                      </div>
                    ))}
                  </div>
                );
              })()}
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

  // CONFRONTO agora tem um unico caminho de geracao (gerar_chaveamento_confronto
  // decide mata-mata vs todos-contra-todos por nivel, dentro da mesma
  // modalidade) -- nao ha mais distincao de tela entre "bracket" e "returno".
  const isCombate = modalidade?.tipo_disputa === "CONFRONTO";

  const { data: equipesTodas } = useQuery({
    queryKey: ["equipes", "para-bracket"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as { id: string; nome: string }[];
    },
    enabled: isCombate,
  });
  const equipePorId = new Map((equipesTodas ?? []).map((e) => [e.id, e.nome]));

  const { data: chavesTodas } = useQuery({
    queryKey: ["chaves", "para-rodadas", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}/chaves", {
        params: { path: { modalidade_id: modalidadeId! } },
      });
      return (data ?? []) as { id: string; nome: string }[];
    },
    enabled: isCombate,
  });
  const chavePorId = new Map((chavesTodas ?? []).map((c) => [c.id, c.nome]));

  const rodadasOrdenadas = [...(rodadas ?? [])].sort((a, b) => a.numero - b.numero);
  const partidasQueries = useQueries({
    queries: isCombate
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
  const rodadaPorId = new Map(rodadasOrdenadas.map((r) => [r.id, r]));
  const todasPartidas = isCombate ? partidasQueries.flatMap((q) => q.data ?? []) : [];

  const ultimaRodadaPorNivel = new Map<number, number>();
  if (isCombate) {
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
  let inicioMataMataPorNivel = new Map<number, number>();
  if (isCombate) {
    const partidasComNumero = todasPartidas.flatMap((p) => {
      const numero = rodadaPorId.get(p.rodada_id ?? "")?.numero;
      return numero == null ? [] : [{ ...p, nivel: p.nivel ?? null, numero }];
    });
    totalRodadasPorNivel = calcularTotalRodadasPorNivel(partidasComNumero);
    inicioMataMataPorNivel = primeiraRodadaMataMataPorNivel(partidasComNumero);
  }

  const [erroChaveamento, setErroChaveamento] = useState<string | null>(null);
  const [mostrarChaveamentoManual, setMostrarChaveamentoManual] = useState(false);
  const [mostrarFaseDeGrupos, setMostrarFaseDeGrupos] = useState(false);

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
        {isCombate ? (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={gerarChaveamento}
              className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white"
            >
              Gerar chaveamento
            </button>
            {modalidade.formato_chaveamento !== "TODOS_CONTRA_TODOS" && (
              <>
                <button
                  type="button"
                  onClick={() => setMostrarFaseDeGrupos(true)}
                  className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
                >
                  Fase de Grupos
                </button>
                <button
                  type="button"
                  onClick={() => setMostrarChaveamentoManual(true)}
                  className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
                >
                  Montar chaveamento manual
                </button>
              </>
            )}
          </div>
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

      {isCombate ? (
        <ul className="space-y-2">
          {rodadasOrdenadas.map((rodada) => (
            <CombateRodada
              key={rodada.id}
              rodada={rodada}
              eventoId={eventoId!}
              modalidadeId={modalidadeId!}
              equipePorId={equipePorId}
              ultimaRodadaPorNivel={ultimaRodadaPorNivel}
              totalRodadasPorNivel={totalRodadasPorNivel}
              inicioMataMataPorNivel={inicioMataMataPorNivel}
              chavePorId={chavePorId}
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

      {mostrarChaveamentoManual && (
        <ChaveamentoManualBuilder
          modalidadeId={modalidadeId!}
          onFechar={() => {
            setMostrarChaveamentoManual(false);
            onMudou();
          }}
        />
      )}

      {mostrarFaseDeGrupos && (
        <FaseDeGruposBuilder
          modalidadeId={modalidadeId!}
          onFechar={() => {
            setMostrarFaseDeGrupos(false);
            onMudou();
          }}
        />
      )}
    </main>
  );
}
