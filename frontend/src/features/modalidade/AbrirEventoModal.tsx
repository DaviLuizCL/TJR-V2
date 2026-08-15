import { useState } from "react";

import { api, extrairErro } from "../../api/client";

export interface ModalidadeParaAbrir {
  id: string;
  nome: string;
  tipo_disputa: string;
  formato_chaveamento?: string | null;
}

interface RodadaGerada {
  id: string;
  numero: number;
}

type ResultadoModalidade = "ok" | string;

async function gerarPrimeiraRodada(modalidade: ModalidadeParaAbrir): Promise<RodadaGerada[]> {
  const ehMataMata =
    modalidade.tipo_disputa === "CONFRONTO" && modalidade.formato_chaveamento === "MATA_MATA";

  if (ehMataMata) {
    const { data, error } = await api.POST("/api/v1/chaveamento/gerar", {
      body: { modalidade_id: modalidade.id } as never,
    });
    if (error || !data) throw new Error(extrairErro(error).mensagem);
    return [data as RodadaGerada];
  }

  const { data, error } = await api.POST("/api/v1/rodadas/gerar", {
    body: { modalidade_id: modalidade.id } as never,
  });
  if (error || !data) throw new Error(extrairErro(error).mensagem);
  return data as RodadaGerada[];
}

export function AbrirEventoModal({
  modalidades,
  onFechar,
  onConcluido,
}: {
  modalidades: ModalidadeParaAbrir[];
  onFechar: () => void;
  onConcluido?: () => void;
}) {
  const [horarios, setHorarios] = useState<Record<string, string>>({});
  const [resultados, setResultados] = useState<Record<string, ResultadoModalidade>>({});
  const [enviando, setEnviando] = useState(false);
  const [concluido, setConcluido] = useState(false);

  async function abrirEvento() {
    setEnviando(true);
    setConcluido(false);
    const novosResultados: Record<string, ResultadoModalidade> = {};

    for (const modalidade of modalidades) {
      try {
        const rodadasGeradas = await gerarPrimeiraRodada(modalidade);

        const horario = horarios[modalidade.id];
        if (horario) {
          const rodada1 = rodadasGeradas.find((r) => r.numero === 1);
          if (rodada1) {
            await api.PATCH("/api/v1/rodadas/{rodada_id}", {
              params: { path: { rodada_id: rodada1.id } },
              body: { horario_inicio: new Date(horario).toISOString() } as never,
            });
          }
        }

        novosResultados[modalidade.id] = "ok";
      } catch (erro) {
        novosResultados[modalidade.id] =
          erro instanceof Error ? erro.message : "Ocorreu um erro inesperado.";
      }
      setResultados({ ...novosResultados });
    }

    setEnviando(false);
    setConcluido(true);
    onConcluido?.();
  }

  const sucessos = Object.values(resultados).filter((r) => r === "ok").length;

  return (
    <div
      role="dialog"
      aria-label="Abrir evento"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-1 text-lg font-semibold text-slate-800">Abrir evento</h2>
        <p className="mb-4 text-sm text-slate-500">
          Gera a primeira rodada de cada modalidade de uma vez (chaveamento inicial no mata-mata,
          rodadas nas demais). O horário é opcional e só marca o início da 1ª rodada — não gera
          agendamento de arena.
        </p>

        <ul className="mb-4 max-h-80 space-y-3 overflow-y-auto">
          {modalidades.map((modalidade) => {
            const resultado = resultados[modalidade.id];
            return (
              <li key={modalidade.id} className="flex items-center gap-3">
                <label
                  htmlFor={`horario-abertura-${modalidade.id}`}
                  className="flex-1 text-sm font-medium text-slate-700"
                >
                  {modalidade.nome}
                </label>
                <input
                  id={`horario-abertura-${modalidade.id}`}
                  type="datetime-local"
                  value={horarios[modalidade.id] ?? ""}
                  onChange={(e) =>
                    setHorarios((atual) => ({ ...atual, [modalidade.id]: e.target.value }))
                  }
                  disabled={enviando}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                />
                {resultado === "ok" && (
                  <span className="text-emerald-700" aria-label="gerado com sucesso">
                    ✓
                  </span>
                )}
                {resultado && resultado !== "ok" && (
                  <span className="text-xs text-red-600">{resultado}</span>
                )}
              </li>
            );
          })}
        </ul>

        {concluido && (
          <p className="mb-4 text-sm font-medium text-slate-700">
            Concluído: {sucessos} de {modalidades.length} modalidades geradas com sucesso.
          </p>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onFechar}
            disabled={enviando}
            className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
          >
            {concluido ? "Fechar" : "Cancelar"}
          </button>
          {!concluido && (
            <button
              type="button"
              onClick={abrirEvento}
              disabled={enviando}
              className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {enviando ? "Abrindo..." : "Abrir evento"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
