import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";

interface PartidaItem {
  id: string;
  rodada_id: string;
  equipe_a_id: string;
  equipe_b_id: string | null;
  vencedor_id: string | null;
  nivel: number | null;
  status: string;
}

interface ModalidadeInfo {
  id: string;
  ficha_unica_entre_niveis: boolean;
  tentativas_por_rodada: number;
}

interface FichaResumo {
  id: string;
  nivel: number | null;
  status: string;
}

interface CriterioItem {
  id: string;
  nome: string;
  tipo: string;
  valores_permitidos: number[] | null;
}

interface FichaCompleta {
  id: string;
  grupos: { id: string; criterios: CriterioItem[] }[];
}

interface EquipeItem {
  id: string;
  nome: string;
}

interface LancamentoItem {
  equipe_id: string;
  tentativa: number;
  partida_id: string | null;
  status: string;
  total: number;
}

interface ItemEnvio {
  criterio_id: string;
  ocorrencias?: number;
  valor?: number;
}

function corResultado(totalA: number, totalB: number, lado: "A" | "B"): string {
  if (totalA === totalB) return "text-slate-800";
  const ganhouA = totalA > totalB;
  return (lado === "A") === ganhouA ? "text-emerald-700" : "text-red-700";
}

const ROTULOS_ESCALA: Record<string, Record<number, string>> = {
  "Resultado do arrasto": { 1: "Arrasto parcial", 2: "Arrasto pro fosso" },
};

function rotuloEscala(nomeCriterio: string, valor: number): string {
  return ROTULOS_ESCALA[nomeCriterio]?.[valor] ?? String(valor);
}

export function PartidaScorerPage() {
  const { eventoId, modalidadeId, rodadaId, partidaId } = useParams<{
    eventoId: string;
    modalidadeId: string;
    rodadaId: string;
    partidaId: string;
  }>();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<number | null>(null);

  const { data: partidas } = useQuery({
    queryKey: ["partidas-da-rodada", rodadaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
        params: { path: { rodada_id: rodadaId! } },
      });
      return (data ?? []) as PartidaItem[];
    },
    enabled: !!rodadaId,
  });
  const partida = partidas?.find((p) => p.id === partidaId);

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

  const { data: fichas } = useQuery({
    queryKey: ["fichas-da-modalidade", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas", {
        params: { query: { modalidade_id: modalidadeId, size: 100 } },
      });
      return (data?.itens ?? []) as FichaResumo[];
    },
    enabled: !!modalidadeId,
  });

  const fichaResumo = fichas?.find(
    (f) =>
      f.status !== "SUBSTITUIDA" &&
      (modalidade?.ficha_unica_entre_niveis ? f.nivel === null : f.nivel === partida?.nivel),
  );

  const { data: ficha } = useQuery({
    queryKey: ["ficha", fichaResumo?.id],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas/{ficha_id}", {
        params: { path: { ficha_id: fichaResumo!.id } },
      });
      return data as FichaCompleta | undefined;
    },
    enabled: !!fichaResumo,
  });

  const { data: equipes } = useQuery({
    queryKey: ["equipes", "para-partida-scorer"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 200 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });
  const equipePorId = new Map((equipes ?? []).map((e) => [e.id, e]));

  const { data: lancamentos } = useQuery({
    queryKey: ["lancamentos-da-rodada", rodadaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/lancamentos", {
        params: { query: { rodada_id: rodadaId, size: 200 } },
      });
      return (data?.itens ?? []) as LancamentoItem[];
    },
    enabled: !!rodadaId,
  });
  const lancamentosDaPartida = (lancamentos ?? []).filter((l) => l.partida_id === partidaId);

  function lancamentoConfirmado(equipeId: string, tentativa: number) {
    return lancamentosDaPartida.find(
      (l) => l.equipe_id === equipeId && l.tentativa === tentativa && l.status === "CONFIRMADO",
    );
  }

  const criterios = ficha?.grupos.flatMap((g) => g.criterios) ?? [];
  const criterioUnico = criterios.length === 1 ? criterios[0] : undefined;
  const valoresOrdenados = [...(criterioUnico?.valores_permitidos ?? [])].sort((a, b) => a - b);

  const tentativasArr = modalidade
    ? Array.from({ length: modalidade.tentativas_por_rodada }, (_, i) => i + 1)
    : [];

  let empateTecnico = false;
  let empatouNoDesempate = false;
  const tentativaDesempate = tentativasArr.length + 1;
  if (partida?.status === "AGENDADA" && partida.equipe_b_id) {
    let vitoriasA = 0;
    let vitoriasB = 0;
    let todasDecididas = true;
    for (const t of tentativasArr) {
      const lancA = lancamentoConfirmado(partida.equipe_a_id, t);
      const lancB = lancamentoConfirmado(partida.equipe_b_id, t);
      if (!lancA || !lancB) {
        todasDecididas = false;
        break;
      }
      if (lancA.total > lancB.total) vitoriasA += 1;
      else if (lancB.total > lancA.total) vitoriasB += 1;
    }
    empateTecnico = todasDecididas && vitoriasA === vitoriasB;

    if (empateTecnico) {
      const lancADesempate = lancamentoConfirmado(partida.equipe_a_id, tentativaDesempate);
      const lancBDesempate = lancamentoConfirmado(partida.equipe_b_id, tentativaDesempate);
      empatouNoDesempate =
        !!lancADesempate && !!lancBDesempate && lancADesempate.total === lancBDesempate.total;
    }
  }

  async function enviarCombate(
    tentativa: number,
    lados: { equipeId: string; itens: ItemEnvio[] }[],
  ) {
    if (!ficha || !rodadaId || !partida) return;
    setErro(null);
    setEnviando(tentativa);

    for (const lado of lados) {
      if (lancamentoConfirmado(lado.equipeId, tentativa)) continue;

      const { data, error } = await api.POST("/api/v1/lancamentos", {
        body: {
          ficha_id: ficha.id,
          rodada_id: rodadaId,
          tentativa,
          equipe_id: lado.equipeId,
          partida_id: partida.id,
          client_operation_id: crypto.randomUUID(),
          itens: lado.itens,
        } as never,
      });
      if (error || !data) {
        setErro(extrairErro(error).mensagem);
        setEnviando(null);
        return;
      }

      const { error: erroConfirmar } = await api.POST(
        "/api/v1/lancamentos/{lancamento_id}/confirmar",
        { params: { path: { lancamento_id: (data as { id: string }).id } } },
      );
      if (erroConfirmar) {
        setErro(extrairErro(erroConfirmar).mensagem);
        setEnviando(null);
        return;
      }
    }

    setEnviando(null);
    await queryClient.invalidateQueries({ queryKey: ["lancamentos-da-rodada", rodadaId] });
    await queryClient.invalidateQueries({ queryKey: ["partidas-da-rodada", rodadaId] });

    const partidasAtualizadas = queryClient.getQueryData<PartidaItem[]>([
      "partidas-da-rodada",
      rodadaId,
    ]);
    const partidaAtual = partidasAtualizadas?.find((p) => p.id === partidaId);
    if (partidaAtual && (partidaAtual.status === "ENCERRADA" || partidaAtual.status === "EMPATADA")) {
      // Partida decidida: volta direto pra lista de Pontuar, sem precisar de
      // clique - agiliza lancar varias partidas seguidas (ex.: bracket
      // grande, dezenas de partidas na mesma rodada).
      navigate(`/eventos/${eventoId}/modalidades/${modalidadeId}/pontuar`);
    }
  }

  function enviarBooleano(tentativa: number, resultado: "A" | "B" | "EMPATE") {
    if (!partida || !criterioUnico) return;
    void enviarCombate(tentativa, [
      {
        equipeId: partida.equipe_a_id,
        itens: [{ criterio_id: criterioUnico.id, ocorrencias: resultado === "A" ? 1 : 0 }],
      },
      {
        equipeId: partida.equipe_b_id!,
        itens: [{ criterio_id: criterioUnico.id, ocorrencias: resultado === "B" ? 1 : 0 }],
      },
    ]);
  }

  function enviarEscala(tentativa: number, resultado: "A" | "B" | "EMPATE", valor?: number) {
    if (!partida || !criterioUnico) return;
    if (resultado === "EMPATE") {
      void enviarCombate(tentativa, [
        { equipeId: partida.equipe_a_id, itens: [{ criterio_id: criterioUnico.id, valor: 0 }] },
        { equipeId: partida.equipe_b_id!, itens: [{ criterio_id: criterioUnico.id, valor: 0 }] },
      ]);
      return;
    }
    const vencedorId = resultado === "A" ? partida.equipe_a_id : partida.equipe_b_id!;
    const perdedorId = resultado === "A" ? partida.equipe_b_id! : partida.equipe_a_id;
    void enviarCombate(tentativa, [
      { equipeId: vencedorId, itens: [{ criterio_id: criterioUnico.id, valor: valor! }] },
      { equipeId: perdedorId, itens: [{ criterio_id: criterioUnico.id, valor: 0 }] },
    ]);
  }

  const carregando =
    !partidas || !modalidade || !fichas || !equipes || !lancamentos || (!!fichaResumo && !ficha);

  if (carregando || !partida) {
    return (
      <main className="p-8">
        <p className="animate-pulse text-slate-500">Carregando...</p>
      </main>
    );
  }

  const nomeA = equipePorId.get(partida.equipe_a_id)?.nome ?? "?";
  const nomeB = partida.equipe_b_id ? (equipePorId.get(partida.equipe_b_id)?.nome ?? "?") : null;

  return (
    <main className="mx-auto max-w-2xl p-8">
      <Link
        to={`/eventos/${eventoId}/modalidades/${modalidadeId}/pontuar`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar para pontuar
      </Link>
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">
        {nomeA} vs {nomeB ?? "?"}
      </h1>

      {partida.status === "ENCERRADA" && (
        <p className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-3 font-medium text-emerald-800">
          Vencedor: {equipePorId.get(partida.vencedor_id ?? "")?.nome ?? "?"}
        </p>
      )}
      {partida.status === "EMPATADA" && (
        <p className="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-3 font-medium text-slate-700">
          Partida empatada
        </p>
      )}
      {empateTecnico && !empatouNoDesempate && (
        <p className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3 font-medium text-amber-800">
          Empate na contagem de combates — decida com o combate extra de desempate abaixo.
        </p>
      )}
      {empatouNoDesempate && (
        <p className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3 font-medium text-amber-800">
          Também empatou no combate de desempate — esta partida precisa de correção do
          coordenador.
        </p>
      )}
      {erro && (
        <div className="mb-4 flex items-start gap-2 rounded border border-red-200 bg-red-50 p-3">
          <span className="text-lg leading-none text-red-600" aria-hidden="true">
            ⚠
          </span>
          <p className="text-sm text-red-700">{erro}</p>
        </div>
      )}

      <ul className="space-y-3">
        {tentativasArr.map(
          (tentativa) => {
            const lancA = lancamentoConfirmado(partida.equipe_a_id, tentativa);
            const lancB = partida.equipe_b_id
              ? lancamentoConfirmado(partida.equipe_b_id, tentativa)
              : undefined;
            const decidido = !!lancA && !!lancB;
            const valoresNaoZero = valoresOrdenados.filter((v) => v !== 0);
            const permiteEmpate = valoresOrdenados.includes(0);

            return (
              <li key={tentativa} className="rounded-lg border border-slate-200 bg-white p-4">
                <p className="mb-2 text-sm font-semibold text-slate-700">Combate {tentativa}</p>

                {decidido ? (
                  <>
                    <p className="text-sm font-medium">
                      <span className={corResultado(lancA!.total, lancB!.total, "A")}>
                        {nomeA}
                      </span>
                      {" vs "}
                      <span className={corResultado(lancA!.total, lancB!.total, "B")}>
                        {nomeB}
                      </span>
                    </p>
                    {lancA!.total === lancB!.total && (
                      <p className="mt-1 text-xs text-slate-500">Empate</p>
                    )}
                  </>
                ) : criterioUnico?.tipo === "BOOLEANO" ? (
                  <div>
                    <p className="mb-2 text-xs font-medium text-slate-500">Defina o vencedor</p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={enviando === tentativa}
                        onClick={() => enviarBooleano(tentativa, "A")}
                        className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                      >
                        {nomeA}
                      </button>
                      <button
                        type="button"
                        disabled={enviando === tentativa}
                        onClick={() => enviarBooleano(tentativa, "B")}
                        className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                      >
                        {nomeB}
                      </button>
                      <button
                        type="button"
                        disabled={enviando === tentativa}
                        onClick={() => enviarBooleano(tentativa, "EMPATE")}
                        className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 disabled:opacity-50"
                      >
                        Empate
                      </button>
                    </div>
                  </div>
                ) : criterioUnico?.tipo === "ESCALA" ? (
                  <div>
                    <p className="mb-2 text-xs font-medium text-slate-500">Defina o resultado</p>
                    <div className="space-y-2">
                      <div>
                        <p className="mb-1 text-xs text-slate-600">{nomeA}</p>
                        <div className="flex flex-wrap gap-2">
                          {valoresNaoZero.map((v) => (
                            <button
                              key={v}
                              type="button"
                              disabled={enviando === tentativa}
                              onClick={() => enviarEscala(tentativa, "A", v)}
                              className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                            >
                              {rotuloEscala(criterioUnico.nome, v)}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="mb-1 text-xs text-slate-600">{nomeB}</p>
                        <div className="flex flex-wrap gap-2">
                          {valoresNaoZero.map((v) => (
                            <button
                              key={v}
                              type="button"
                              disabled={enviando === tentativa}
                              onClick={() => enviarEscala(tentativa, "B", v)}
                              className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                            >
                              {rotuloEscala(criterioUnico.nome, v)}
                            </button>
                          ))}
                        </div>
                      </div>
                      {permiteEmpate && (
                        <button
                          type="button"
                          disabled={enviando === tentativa}
                          onClick={() => enviarEscala(tentativa, "EMPATE")}
                          className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 disabled:opacity-50"
                        >
                          Empate
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <Link
                    to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodadaId}/lancamentos/novo?partidaId=${partidaId}`}
                    className="text-sm font-medium text-slate-700 underline"
                  >
                    Lançar pela ficha completa →
                  </Link>
                )}
              </li>
            );
          },
        )}
      </ul>

      {empateTecnico &&
        (() => {
          const lancA = lancamentoConfirmado(partida.equipe_a_id, tentativaDesempate);
          const lancB = partida.equipe_b_id
            ? lancamentoConfirmado(partida.equipe_b_id, tentativaDesempate)
            : undefined;
          const decidido = !!lancA && !!lancB;
          const valoresNaoZero = valoresOrdenados.filter((v) => v !== 0);

          return (
            <div className="mt-4 rounded-lg border-2 border-amber-300 bg-white p-4">
              <p className="mb-2 text-sm font-semibold text-amber-700">
                Combate extra (desempate)
              </p>

              {decidido ? (
                <p className="text-sm font-medium">
                  <span className={corResultado(lancA!.total, lancB!.total, "A")}>{nomeA}</span>
                  {" vs "}
                  <span className={corResultado(lancA!.total, lancB!.total, "B")}>{nomeB}</span>
                </p>
              ) : criterioUnico?.tipo === "BOOLEANO" ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={enviando === tentativaDesempate}
                    onClick={() => enviarBooleano(tentativaDesempate, "A")}
                    className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                  >
                    {nomeA}
                  </button>
                  <button
                    type="button"
                    disabled={enviando === tentativaDesempate}
                    onClick={() => enviarBooleano(tentativaDesempate, "B")}
                    className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                  >
                    {nomeB}
                  </button>
                </div>
              ) : criterioUnico?.tipo === "ESCALA" ? (
                <div className="space-y-2">
                  <div>
                    <p className="mb-1 text-xs text-slate-600">{nomeA}</p>
                    <div className="flex flex-wrap gap-2">
                      {valoresNaoZero.map((v) => (
                        <button
                          key={v}
                          type="button"
                          disabled={enviando === tentativaDesempate}
                          onClick={() => enviarEscala(tentativaDesempate, "A", v)}
                          className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                        >
                          {rotuloEscala(criterioUnico.nome, v)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-xs text-slate-600">{nomeB}</p>
                    <div className="flex flex-wrap gap-2">
                      {valoresNaoZero.map((v) => (
                        <button
                          key={v}
                          type="button"
                          disabled={enviando === tentativaDesempate}
                          onClick={() => enviarEscala(tentativaDesempate, "B", v)}
                          className="rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                        >
                          {rotuloEscala(criterioUnico.nome, v)}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <Link
                  to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodadaId}/lancamentos/novo?partidaId=${partidaId}`}
                  className="text-sm font-medium text-slate-700 underline"
                >
                  Lançar pela ficha completa →
                </Link>
              )}
            </div>
          );
        })()}
    </main>
  );
}
