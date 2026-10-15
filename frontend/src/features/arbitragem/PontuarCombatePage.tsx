import { useQueries, useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { PageHeader } from "../../components/PageHeader";
import { iconeModalidade } from "../../lib/modalidade-icone";
import { rotuloNivel } from "../../lib/nivel";

interface ModalidadeInfo {
  id: string;
  nome: string;
}

const CLASSES_FASE_NEUTRA = "bg-slate-100 text-slate-700 border border-slate-300";

interface RodadaItem {
  id: string;
  numero: number;
}

interface EquipeItem {
  id: string;
  nome: string;
}

interface PartidaItem {
  id: string;
  rodada_id: string;
  equipe_a_id: string;
  equipe_b_id: string | null;
  vencedor_id: string | null;
  nivel: number | null;
  status: string;
  criado_em: string;
  formato_chaveamento?: string;
  chave_id?: string | null;
}

interface ChaveItem {
  id: string;
  nome: string;
}

function corDaEquipe(partida: PartidaItem, equipeId: string): string {
  if (partida.status !== "ENCERRADA" || !partida.vencedor_id) return "text-slate-800";
  return partida.vencedor_id === equipeId ? "text-emerald-700" : "text-red-700";
}

export function PontuarCombatePage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const nivelFiltro = searchParams.get("nivel") ?? "";
  const ehCoordenador = useAuthStore((state) => state.usuario?.papel) === "COORDENADOR";

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
  const rodadaPorId = new Map(rodadasOrdenadas.map((r) => [r.id, r]));

  const { data: equipesTodas } = useQuery({
    queryKey: ["equipes", "para-pontuar-combate"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });
  const equipePorId = new Map((equipesTodas ?? []).map((e) => [e.id, e.nome]));

  const { data: chavesTodas } = useQuery({
    queryKey: ["chaves", "para-pontuar-combate", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}/chaves", {
        params: { path: { modalidade_id: modalidadeId! } },
      });
      return (data ?? []) as ChaveItem[];
    },
    enabled: !!modalidadeId,
  });
  const chavePorId = new Map((chavesTodas ?? []).map((c) => [c.id, c.nome]));

  const partidasQueries = useQueries({
    queries: rodadasOrdenadas.map((rodada) => ({
      queryKey: ["partidas-da-rodada", rodada.id],
      queryFn: async () => {
        const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
          params: { path: { rodada_id: rodada.id } },
        });
        return (data ?? []) as PartidaItem[];
      },
    })),
  });

  const carregando =
    !modalidade || !rodadas || !equipesTodas || partidasQueries.some((q) => q.isLoading);

  if (carregando) {
    return (
      <main className="px-4 py-6 sm:p-8">
        <p className="animate-pulse text-slate-500">Carregando...</p>
      </main>
    );
  }

  const todasPartidas: PartidaItem[] = partidasQueries.flatMap((q) => q.data ?? []);
  todasPartidas.sort((a, b) => {
    const rodadaA = rodadaPorId.get(a.rodada_id)?.numero ?? 0;
    const rodadaB = rodadaPorId.get(b.rodada_id)?.numero ?? 0;
    if (rodadaA !== rodadaB) return rodadaA - rodadaB;
    const nivelA = a.nivel ?? 0;
    const nivelB = b.nivel ?? 0;
    if (nivelA !== nivelB) return nivelA - nivelB;
    return a.criado_em.localeCompare(b.criado_em);
  });

  const niveisDisponiveis = Array.from(
    new Set(todasPartidas.map((p) => p.nivel).filter((n): n is number => n != null)),
  ).sort((a, b) => a - b);
  const partidas = todasPartidas.filter(
    (p) => nivelFiltro === "" || p.nivel === Number(nivelFiltro),
  );

  function grupoDaPartida(partida: PartidaItem): { label: string; classes: string; ordem: number } {
    // Partida de fase de grupos (com chave) -- rotula pelo nome da chave, e
    // fica sempre no fim (ordem alta): o mata-mata pos-grupos e o que importa.
    if (partida.chave_id != null) {
      const nomeChave = chavePorId.get(partida.chave_id) ?? "Fase de Grupos";
      return { label: nomeChave, classes: CLASSES_FASE_NEUTRA, ordem: 1000 };
    }
    if (partida.formato_chaveamento === "TODOS_CONTRA_TODOS") {
      return { label: "Fase de Grupos", classes: CLASSES_FASE_NEUTRA, ordem: 0 };
    }
    // Eliminatoria: so "Rodada N". O chaveamento e montado na mao (out/2026),
    // entao o sistema nao tem como saber se uma rodada e final ou semifinal;
    // chutar o nome confundia o coordenador na hora (pedido de 14/10/2026).
    // Rodada mais nova primeiro (ordem menor).
    const numero = rodadaPorId.get(partida.rodada_id)?.numero ?? 0;
    return { label: `Rodada ${numero}`, classes: CLASSES_FASE_NEUTRA, ordem: -numero };
  }

  const grupos: { label: string; classes: string; ordem: number; itens: PartidaItem[] }[] = [];
  const indicePorLabel = new Map<string, number>();
  for (const partida of partidas) {
    const info = grupoDaPartida(partida);
    if (!indicePorLabel.has(info.label)) {
      indicePorLabel.set(info.label, grupos.length);
      grupos.push({ ...info, itens: [] });
    }
    grupos[indicePorLabel.get(info.label)!].itens.push(partida);
  }
  // Rodada/fase mais nova primeiro (ordem menor = fase mais recente/final) -
  // e o que o coordenador precisa olhar assim que a rodada anterior fecha,
  // sem ter que rolar a tela passando pelas rodadas ja resolvidas.
  grupos.sort((a, b) => a.ordem - b.ordem);
  for (const grupo of grupos) {
    grupo.itens.sort((a, b) => {
      const decididaA = a.status === "ENCERRADA" || a.status === "EMPATADA";
      const decididaB = b.status === "ENCERRADA" || b.status === "EMPATADA";
      return Number(decididaA) - Number(decididaB);
    });
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        voltar={{ para: `/eventos/${eventoId}/competicoes?aba=combate`, rotulo: "Voltar para combates" }}
        sobretitulo="Pontuar combate"
        titulo={
          <>
            <span aria-hidden="true">{iconeModalidade(modalidade!.nome)} </span>
            {modalidade!.nome}
          </>
        }
        descricao="Toque num confronto em aberto pra lançar o resultado. Os já decididos ficam esmaecidos no fim de cada rodada."
      />

      {niveisDisponiveis.length > 1 && (
        <div className="card mb-6 p-4">
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="filtro-nivel">
            Filtrar por nivel
          </label>
          <select
            id="filtro-nivel"
            value={nivelFiltro}
            onChange={(e) => {
              const valor = e.target.value;
              setSearchParams(valor ? { nivel: valor } : {});
            }}
            className="min-h-12 w-full max-w-xs rounded-lg border border-slate-300 px-3 py-2"
          >
            <option value="">Todos os níveis</option>
            {niveisDisponiveis.map((nivel) => (
              <option key={nivel} value={nivel}>
                {rotuloNivel(nivel)}
              </option>
            ))}
          </select>
        </div>
      )}

      {todasPartidas.length === 0 && (
        <div className="card p-6 text-center text-slate-600">
          <p className="text-4xl" aria-hidden="true">⚔️</p>
          <p className="mt-2">
            Nenhuma partida criada ainda. A coordenação monta os confrontos em Ver confrontos →
            Montar chaveamento manual.
          </p>
        </div>
      )}
      {todasPartidas.length > 0 && partidas.length === 0 && (
        <p className="text-slate-500">
          Nenhuma partida do {nivelFiltro ? rotuloNivel(Number(nivelFiltro)) : "nível"} nesta
          modalidade.
        </p>
      )}

      <div className="space-y-8">
        {grupos.map((grupo) => (
          <section key={grupo.label}>
            <h2
              className={`mb-3 inline-block rounded-full px-4 py-1 font-display text-sm font-bold uppercase tracking-widest ${grupo.classes}`}
            >
              {grupo.label}
            </h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {grupo.itens.map((partida) => {
                const rodada = rodadaPorId.get(partida.rodada_id);
                const nomeA = equipePorId.get(partida.equipe_a_id) ?? "Equipe";
                const nomeB = partida.equipe_b_id
                  ? (equipePorId.get(partida.equipe_b_id) ?? "Equipe")
                  : null;
                const decidida = partida.status === "ENCERRADA" || partida.status === "EMPATADA";

                const corpo = (
                  <>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Rodada {rodada?.numero}
                      {partida.nivel != null ? ` · ${rotuloNivel(partida.nivel)}` : ""}
                    </p>
                    <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                      <p className="min-w-0 break-words font-display text-lg font-bold leading-tight">
                        <span className={corDaEquipe(partida, partida.equipe_a_id)}>{nomeA}</span>
                      </p>
                      <span
                        aria-label="contra"
                        className="rounded-md bg-slate-100 px-2 py-1 font-display text-xs font-bold text-plasma ring-1 ring-plasma/40"
                      >
                        VS
                      </span>
                      <p className="min-w-0 break-words text-right font-display text-lg font-bold leading-tight">
                        {nomeB ? (
                          <span className={corDaEquipe(partida, partida.equipe_b_id!)}>{nomeB}</span>
                        ) : (
                          <span className="text-slate-400">(bye)</span>
                        )}
                      </p>
                    </div>
                    {partida.status === "EMPATADA" && (
                      <p className="mt-3 text-sm font-semibold text-slate-500">Empate</p>
                    )}
                    {partida.status === "ENCERRADA" && partida.vencedor_id && (
                      <p className="mt-3 text-sm font-semibold text-emerald-700">
                        🏆 Vencedor: {equipePorId.get(partida.vencedor_id) ?? "?"}
                      </p>
                    )}
                  </>
                );

                const linkPartida = `/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${partida.rodada_id}/partidas/${partida.id}/pontuar${nivelFiltro ? `?nivel=${nivelFiltro}` : ""}`;

                if (decidida) {
                  return (
                    <li key={partida.id}>
                      <div className="rounded-xl border border-slate-200 bg-slate-100/60 p-4">
                        <div className="opacity-75">{corpo}</div>
                        {ehCoordenador && partida.equipe_b_id && (
                          <Link
                            to={linkPartida}
                            className="btn-secondary mt-3 min-h-10"
                          >
                            ✏️ Corrigir
                          </Link>
                        )}
                      </div>
                    </li>
                  );
                }

                return (
                  <li key={partida.id}>
                    <Link
                      to={linkPartida}
                      className="card block p-4 hover:border-neon/60 hover:shadow-glow"
                    >
                      {corpo}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </main>
  );
}
