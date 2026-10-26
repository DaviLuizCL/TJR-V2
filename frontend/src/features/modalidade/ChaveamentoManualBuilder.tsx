import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { type DragEvent, useState } from "react";

import { api, extrairErro } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { rotuloNivel } from "../../lib/nivel";

const BYE = "__BYE__";

type Formato = "TODOS_CONTRA_TODOS" | "MATA_MATA";

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
  comoPagina = false,
}: {
  modalidadeId: string;
  onFechar?: () => void;
  // true = conteudo direto na pagina (cartao da Administracao); false = janela
  // por cima da tela de Rodadas.
  comoPagina?: boolean;
}) {
  const queryClient = useQueryClient();
  const [nivelSelecionado, setNivelSelecionado] = useState<number | "">("");
  const [equipeAId, setEquipeAId] = useState("");
  const [equipeBId, setEquipeBId] = useState("");
  // null = ainda nao mexeu: usa a ultima rodada que ja existe (ou 1).
  const [rodadaDigitada, setRodadaDigitada] = useState<string | null>(null);
  const [formato, setFormato] = useState<Formato>("MATA_MATA");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [arrastandoId, setArrastandoId] = useState<string | null>(null);
  const [slotSobre, setSlotSobre] = useState<"A" | "B" | null>(null);

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

  const ultimaRodada = rodadasOrdenadas[rodadasOrdenadas.length - 1]?.numero ?? 1;
  const rodadaTexto = rodadaDigitada ?? String(ultimaRodada);
  const numeroAlvo = Number(rodadaTexto);
  const rodadaValida = Number.isInteger(numeroAlvo) && numeroAlvo >= 1;

  const idsComPartida = new Set(
    todasPartidas
      .filter((p) => p.numero === numeroAlvo)
      .flatMap((p) => [p.equipe_a_id, p.equipe_b_id].filter((x): x is string => !!x)),
  );
  const equipesDoNivel = equipesDaModalidade.filter((e) => e.nivel === nivelAtivo);
  const elegiveis = equipesDoNivel.filter(
    (e) => !idsComPartida.has(e.id) && e.presente !== false,
  );
  const partidasDoNivel = todasPartidas.filter(
    (p) => p.nivel === nivelAtivo && p.numero === numeroAlvo,
  );
  const aceitaBye = formato === "MATA_MATA";

  // Toque na A, toque na B: tocar numa escolhida desmarca; com as duas ja
  // escolhidas, o toque troca a B.
  function tocarEquipe(id: string) {
    if (id === equipeAId) {
      setEquipeAId(equipeBId === BYE ? "" : equipeBId);
      if (equipeBId === BYE) return;
      setEquipeBId("");
      return;
    }
    if (id === equipeBId) {
      setEquipeBId("");
      return;
    }
    if (!equipeAId) setEquipeAId(id);
    else setEquipeBId(id);
  }

  function tocarBye() {
    if (equipeBId === BYE) setEquipeBId("");
    else if (equipeAId) setEquipeBId(BYE);
  }

  // Arrastar o nome pro quadro A ou B (o toque continua valendo). Soltar num
  // quadro ocupado troca a equipe dele; se a equipe estava no outro lado,
  // ela sai de la pra nao repetir.
  function soltarNoLado(lado: "A" | "B") {
    const id = arrastandoId;
    setArrastandoId(null);
    setSlotSobre(null);
    if (!id) return;
    if (lado === "A") {
      if (id === BYE) return;
      if (equipeBId === id) setEquipeBId("");
      setEquipeAId(id);
    } else {
      if (equipeAId === id) setEquipeAId("");
      setEquipeBId(id);
    }
  }

  function propsArrastavel(id: string) {
    return {
      draggable: true,
      onDragStart: (evento: DragEvent) => {
        evento.dataTransfer?.setData("text/plain", id);
        setArrastandoId(id);
      },
      onDragEnd: () => {
        setArrastandoId(null);
        setSlotSobre(null);
      },
    };
  }

  function propsSlot(lado: "A" | "B") {
    return {
      "data-testid": lado === "A" ? "slot-a" : "slot-b",
      onDragOver: (evento: DragEvent) => {
        evento.preventDefault();
        setSlotSobre(lado);
      },
      onDragLeave: () => setSlotSobre(null),
      onDrop: (evento: DragEvent) => {
        evento.preventDefault();
        soltarNoLado(lado);
      },
      className: `rounded border-2 border-dashed px-3 py-3 ${
        slotSobre === lado ? "border-neon bg-neon-soft" : "border-slate-300"
      }`,
    };
  }

  async function invalidar() {
    await queryClient.invalidateQueries({ queryKey: ["rodadas", "chaveamento-manual-builder"] });
    await queryClient.invalidateQueries({ queryKey: ["partidas", "chaveamento-manual-builder"] });
  }

  async function salvar() {
    if (!equipeAId || !equipeBId || !rodadaValida) return;
    setEnviando(true);
    setErro(null);
    const { error } = await api.POST(
      "/api/v1/modalidades/{modalidade_id}/chaveamento/partida-manual",
      {
        params: { path: { modalidade_id: modalidadeId } },
        body: {
          equipe_a_id: equipeAId,
          equipe_b_id: equipeBId === BYE ? null : equipeBId,
          rodada_numero: numeroAlvo,
          formato_chaveamento: formato,
        },
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

  const conteudo = (
      <>
        {!comoPagina && (
          <h2 className="mb-1 text-lg font-semibold text-slate-800">Montar chaveamento manual</h2>
        )}
        <p className="mb-4 text-sm text-slate-500">
          Escolha a rodada, o tipo e as duas equipes e salve — o confronto já vira um card pro
          árbitro pontuar. O sistema não gera nem avança chaveamento sozinho: semifinal e final
          também são montadas aqui.
        </p>

        {niveis.length > 0 && (
          <div className="mb-4">
            <p className="mb-1 text-sm font-medium text-slate-700">Nível</p>
            <div role="group" aria-label="Nível" className="flex flex-wrap gap-2">
              {niveis.map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-pressed={n === nivelAtivo}
                  onClick={() => {
                    setNivelSelecionado(n);
                    setEquipeAId("");
                    setEquipeBId("");
                  }}
                  className={`min-h-12 rounded border px-4 text-sm font-semibold ${
                    n === nivelAtivo
                      ? "border-neon bg-neon-soft text-slate-900"
                      : "border-slate-300 text-slate-700"
                  }`}
                >
                  {rotuloNivel(n)}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mb-4 flex gap-3">
          <div className="w-24">
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="rodada-manual">
              Rodada
            </label>
            <input
              id="rodada-manual"
              type="number"
              min={1}
              value={rodadaTexto}
              onChange={(e) => {
                setRodadaDigitada(e.target.value);
                setEquipeAId("");
                setEquipeBId("");
              }}
              className="w-full rounded border border-slate-300 px-3 py-2"
            />
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="tipo-manual">
              Tipo
            </label>
            <select
              id="tipo-manual"
              value={formato}
              onChange={(e) => {
                const novo = e.target.value as Formato;
                setFormato(novo);
                if (novo !== "MATA_MATA" && equipeBId === BYE) setEquipeBId("");
              }}
              className="w-full rounded border border-slate-300 px-3 py-2"
            >
              <option value="TODOS_CONTRA_TODOS">Fase de grupos (aceita empate)</option>
              <option value="MATA_MATA">Eliminatória (sem empate)</option>
            </select>
          </div>
        </div>

        <div className="mb-3 grid grid-cols-2 gap-3 text-sm">
          <div {...propsSlot("A")}>
            <span className="block text-xs uppercase tracking-wide text-slate-500">Equipe A</span>
            <span data-testid="lado-a" className="font-semibold text-slate-800">
              {equipePorId.get(equipeAId)?.nome ?? "—"}
            </span>
          </div>
          <div {...propsSlot("B")}>
            <span className="block text-xs uppercase tracking-wide text-slate-500">Equipe B</span>
            <span data-testid="lado-b" className="font-semibold text-slate-800">
              {equipeBId === BYE ? "Bye (sem adversário)" : (equipePorId.get(equipeBId)?.nome ?? "—")}
            </span>
          </div>
        </div>

        <p className="mb-2 text-sm font-medium text-slate-700">
          Toque nas duas equipes do confronto (ou arraste o nome pro quadro A ou B)
        </p>
        <div role="group" aria-label="Equipes disponíveis" className="mb-4 flex flex-wrap gap-2">
          {elegiveis.map((e) => {
            const lado = e.id === equipeAId ? "A" : e.id === equipeBId ? "B" : null;
            return (
              <button
                key={e.id}
                type="button"
                {...propsArrastavel(e.id)}
                aria-pressed={lado !== null}
                onClick={() => tocarEquipe(e.id)}
                className={`min-h-12 rounded border px-3 text-sm font-medium ${
                  lado
                    ? "border-neon bg-neon-soft text-slate-900"
                    : "border-slate-300 text-slate-700"
                }`}
              >
                {e.nome}
                {lado && <span className="ml-2 chip">{lado}</span>}
              </button>
            );
          })}
          {aceitaBye && (
            <button
              type="button"
              {...propsArrastavel(BYE)}
              aria-pressed={equipeBId === BYE}
              onClick={tocarBye}
              disabled={!equipeAId}
              className={`min-h-12 rounded border border-dashed px-3 text-sm font-medium disabled:opacity-40 ${
                equipeBId === BYE
                  ? "border-neon bg-neon-soft text-slate-900"
                  : "border-slate-300 text-slate-500"
              }`}
            >
              Bye (sem adversário)
            </button>
          )}
          {elegiveis.length === 0 && (
            <p className="text-sm text-slate-500">
              Todas as equipes deste nível já têm confronto nesta rodada.
            </p>
          )}
        </div>

        {erro && <Aviso tipo="erro" className="mb-4">{erro}</Aviso>}

        <button
          type="button"
          onClick={salvar}
          disabled={enviando || !equipeAId || !equipeBId || !rodadaValida}
          className="btn-primary mb-6 text-sm"
        >
          {enviando ? "Salvando..." : "Salvar confronto"}
        </button>

        <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-slate-500">
          Confrontos já montados neste nível nesta rodada
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

        {onFechar && (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={onFechar}
              className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
            >
              Fechar
            </button>
          </div>
        )}
      </>
  );

  if (comoPagina) return <section>{conteudo}</section>;

  return (
    <div
      role="dialog"
      aria-label="Montar chaveamento manual"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        {conteudo}
      </div>
    </div>
  );
}
