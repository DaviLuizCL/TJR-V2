import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { rotuloNivel } from "../../lib/nivel";

interface ModalidadeChaveamento {
  id: string;
  nome: string;
  tipo_disputa: string;
}

interface RodadaItem {
  id: string;
  numero: number;
}

interface PartidaItem {
  id: string;
  equipe_a_id: string;
  equipe_b_id: string | null;
  vencedor_id: string | null;
  status: string;
  nivel: number | null;
  formato_chaveamento?: string;
  chave_id?: string | null;
}

function ladoClasses(vencedorId: string | null, equipeId: string): string {
  return vencedorId === equipeId ? "font-semibold text-emerald-700" : "text-slate-700";
}

function ColunaRodada({
  rodada,
  partidas,
  equipePorId,
  chavePorId,
}: {
  rodada: RodadaItem;
  partidas: PartidaItem[];
  equipePorId: Map<string, string>;
  chavePorId: Map<string, string>;
}) {
  return (
    <div className="w-64 shrink-0">
      <h2 className="mb-2 text-center text-sm font-semibold uppercase tracking-wide text-slate-500">
        Rodada {rodada.numero}
      </h2>
      <div className="space-y-3">
        {partidas.map((partida) => (
          <div key={partida.id} className="rounded border border-slate-200 bg-white p-3 text-sm">
            {partida.chave_id != null && (
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                {chavePorId.get(partida.chave_id) ?? "Fase de Grupos"}
              </p>
            )}
            <p className={ladoClasses(partida.vencedor_id, partida.equipe_a_id)}>
              {equipePorId.get(partida.equipe_a_id) ?? "?"}
            </p>
            {partida.equipe_b_id ? (
              <p className={ladoClasses(partida.vencedor_id, partida.equipe_b_id)}>
                {equipePorId.get(partida.equipe_b_id) ?? "?"}
              </p>
            ) : (
              <p className="text-slate-400">(bye)</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ResetarChaveamentoModal({
  modalidadeId,
  onFechar,
  onResetado,
}: {
  modalidadeId: string;
  onFechar: () => void;
  onResetado: () => void;
}) {
  const [justificativa, setJustificativa] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    const { error } = await api.POST("/api/v1/modalidades/{modalidade_id}/chaveamento/reset", {
      params: { path: { modalidade_id: modalidadeId } },
      body: { justificativa: justificativa.trim() },
    });
    setEnviando(false);

    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }

    onResetado();
  }

  return (
    <div
      role="dialog"
      aria-label="Resetar chaveamento"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-1 text-lg font-semibold text-slate-800">Resetar chaveamento</h2>
        <p className="mb-4 text-sm text-slate-500">
          Apaga de verdade todas as rodadas, partidas e lançamentos já feitos nessa modalidade,
          pra recomeçar o chaveamento do zero (ex.: formato errado configurado por engano). Essa
          ação não pode ser desfeita.
        </p>

        <label
          htmlFor="justificativa-reset-chaveamento"
          className="mb-1 block text-sm font-medium text-slate-700"
        >
          Justificativa
        </label>
        <textarea
          id="justificativa-reset-chaveamento"
          value={justificativa}
          onChange={(e) => setJustificativa(e.target.value)}
          disabled={enviando}
          rows={3}
          className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-sm"
        />

        {erro && <p className="mb-4 text-sm text-red-600">{erro}</p>}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onFechar}
            disabled={enviando}
            className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={confirmar}
            disabled={enviando || justificativa.trim().length === 0}
            className="rounded bg-red-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {enviando ? "Resetando..." : "Confirmar reset"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ChaveamentoPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const queryClient = useQueryClient();
  const ehCoordenador = useAuthStore((state) => state.usuario?.papel) === "COORDENADOR";
  const [modalidadeId, setModalidadeId] = useState("");
  const [nivelSelecionado, setNivelSelecionado] = useState("");
  const [mostrarReset, setMostrarReset] = useState(false);

  const { data: modalidades } = useQuery({
    queryKey: ["modalidades-chaveamento", eventoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades", {
        params: { query: { evento_id: eventoId, size: 200 } },
      });
      return (data?.itens ?? []).filter(
        (m) => m.tipo_disputa === "CONFRONTO",
      ) as ModalidadeChaveamento[];
    },
    enabled: !!eventoId,
  });

  const modalidadeAtivaId = modalidadeId || modalidades?.[0]?.id || "";
  const modalidadeAtiva = modalidades?.find((m) => m.id === modalidadeAtivaId);

  const { data: rodadas } = useQuery({
    queryKey: ["rodadas-chaveamento", modalidadeAtivaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas", {
        params: { query: { modalidade_id: modalidadeAtivaId, size: 200 } },
      });
      return (data?.itens ?? []) as RodadaItem[];
    },
    enabled: !!modalidadeAtivaId,
  });

  const rodadasOrdenadas = [...(rodadas ?? [])].sort((a, b) => a.numero - b.numero);

  const partidasQueries = useQueries({
    queries: rodadasOrdenadas.map((rodada) => ({
      queryKey: ["partidas-chaveamento", rodada.id],
      queryFn: async () => {
        const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
          params: { path: { rodada_id: rodada.id } },
        });
        return (data ?? []) as PartidaItem[];
      },
    })),
  });

  const { data: equipesTodas } = useQuery({
    queryKey: ["equipes", "para-chaveamento"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as { id: string; nome: string }[];
    },
    enabled: !!modalidadeAtivaId,
  });
  const equipePorId = new Map((equipesTodas ?? []).map((e) => [e.id, e.nome]));

  const { data: chavesTodas } = useQuery({
    queryKey: ["chaves", "para-chaveamento", modalidadeAtivaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}/chaves", {
        params: { path: { modalidade_id: modalidadeAtivaId } },
      });
      return (data ?? []) as { id: string; nome: string }[];
    },
    enabled: !!modalidadeAtivaId,
  });
  const chavePorId = new Map((chavesTodas ?? []).map((c) => [c.id, c.nome]));

  const partidasPorRodada = new Map<string, PartidaItem[]>(
    rodadasOrdenadas.map((rodada, i) => [rodada.id, partidasQueries[i]?.data ?? []]),
  );

  const todasPartidas = rodadasOrdenadas.flatMap(
    (rodada) => partidasPorRodada.get(rodada.id) ?? [],
  );
  const niveisDisponiveis = Array.from(
    new Set(todasPartidas.map((p) => p.nivel).filter((n): n is number => n !== null)),
  ).sort((a, b) => a - b);

  const nivelSelecionadoNumero = nivelSelecionado ? Number(nivelSelecionado) : undefined;
  const nivelAtivo = niveisDisponiveis.includes(nivelSelecionadoNumero ?? -1)
    ? nivelSelecionadoNumero
    : niveisDisponiveis[0];

  const filtrandoPorNivel = niveisDisponiveis.length > 0;

  const colunas = rodadasOrdenadas
    .map((rodada) => {
      const partidas = partidasPorRodada.get(rodada.id) ?? [];
      return {
        rodada,
        partidas: filtrandoPorNivel ? partidas.filter((p) => p.nivel === nivelAtivo) : partidas,
      };
    })
    .filter(({ partidas }) => !filtrandoPorNivel || partidas.length > 0);

  function calcularBanner(): string | null {
    if (!modalidadeAtiva || !filtrandoPorNivel) return null;
    const partidasDoNivel = todasPartidas.filter((p) => p.nivel === nivelAtivo);
    if (partidasDoNivel.length === 0) return null;

    // Formato e por nivel (Partida.formato_chaveamento), nao mais um campo
    // unico da modalidade -- todas as partidas de um nivel compartilham o
    // mesmo formato, por construcao (gerar_chaveamento_confronto).
    const formatoDoNivel = partidasDoNivel[0]?.formato_chaveamento;

    if (formatoDoNivel === "MATA_MATA") {
      const rodadasComNivel = rodadasOrdenadas.filter((r) =>
        (partidasPorRodada.get(r.id) ?? []).some((p) => p.nivel === nivelAtivo),
      );
      if (rodadasComNivel.length === 0) return null;
      const ultimaRodada = rodadasComNivel[rodadasComNivel.length - 1];
      const partidasDaUltima = (partidasPorRodada.get(ultimaRodada.id) ?? []).filter(
        (p) => p.nivel === nivelAtivo,
      );
      if (partidasDaUltima.length === 1 && partidasDaUltima[0].status === "ENCERRADA") {
        const nomeCampeao = equipePorId.get(partidasDaUltima[0].vencedor_id ?? "") ?? "?";
        return `Campeão: ${nomeCampeao}`;
      }
      return null;
    }

    if (formatoDoNivel === "TODOS_CONTRA_TODOS") {
      const finalizado = partidasDoNivel.every(
        (p) => p.status === "ENCERRADA" || p.status === "EMPATADA",
      );
      return finalizado ? "Returno finalizado" : null;
    }

    return null;
  }

  const banner = calcularBanner();

  return (
    <div>
      {modalidades && modalidades.length === 0 && (
        <p className="text-slate-500">Nenhuma modalidade de combate neste evento.</p>
      )}

      {modalidades && modalidades.length > 0 && (
        <>
          <div className="mb-6 flex flex-wrap gap-4">
            <div>
              <label
                className="mb-1 block text-sm font-medium text-slate-700"
                htmlFor="modalidade-chaveamento"
              >
                Modalidade
              </label>
              <select
                id="modalidade-chaveamento"
                value={modalidadeAtivaId}
                onChange={(e) => {
                  setModalidadeId(e.target.value);
                  setNivelSelecionado("");
                }}
                className="w-full max-w-sm rounded border border-slate-300 px-3 py-2"
              >
                {modalidades.map((modalidade) => (
                  <option key={modalidade.id} value={modalidade.id}>
                    {modalidade.nome}
                  </option>
                ))}
              </select>
            </div>

            {niveisDisponiveis.length > 1 && (
              <div>
                <label
                  className="mb-1 block text-sm font-medium text-slate-700"
                  htmlFor="nivel-chaveamento"
                >
                  Nivel
                </label>
                <select
                  id="nivel-chaveamento"
                  value={nivelAtivo}
                  onChange={(e) => setNivelSelecionado(e.target.value)}
                  className="w-full max-w-xs rounded border border-slate-300 px-3 py-2"
                >
                  {niveisDisponiveis.map((nivel) => (
                    <option key={nivel} value={nivel}>
                      {rotuloNivel(nivel)}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {rodadas && rodadas.length === 0 && (
            <p className="text-slate-500">
              Chaveamento ainda nao foi gerado para esta modalidade.
            </p>
          )}

          {ehCoordenador && rodadas && rodadas.length > 0 && (
            <button
              type="button"
              onClick={() => setMostrarReset(true)}
              className="mb-4 rounded border border-red-300 px-4 py-2 text-sm font-medium text-red-700"
            >
              Resetar chaveamento
            </button>
          )}

          {banner && (
            <p className="mb-4 rounded bg-emerald-50 px-4 py-2 font-medium text-emerald-800">
              {banner}
            </p>
          )}

          {rodadas && rodadas.length > 0 && (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {colunas.map(({ rodada, partidas }) => (
                <ColunaRodada
                  key={rodada.id}
                  rodada={rodada}
                  partidas={partidas}
                  equipePorId={equipePorId}
                  chavePorId={chavePorId}
                />
              ))}
            </div>
          )}
        </>
      )}

      {mostrarReset && (
        <ResetarChaveamentoModal
          modalidadeId={modalidadeAtivaId}
          onFechar={() => setMostrarReset(false)}
          onResetado={() => {
            setMostrarReset(false);
            void queryClient.invalidateQueries({ queryKey: ["rodadas-chaveamento"] });
          }}
        />
      )}
    </div>
  );
}
