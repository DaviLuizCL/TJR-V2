import { useQueries, useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import {
  calcularTotalRodadasPorNivel,
  nomeFase,
  primeiraRodadaMataMataPorNivel,
} from "../../lib/fase-chaveamento";
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
      <main className="p-8">
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

  const partidasComNumero = todasPartidas.map((p) => ({
    ...p,
    numero: rodadaPorId.get(p.rodada_id)?.numero ?? 0,
  }));
  const totalRodadasPorNivel = calcularTotalRodadasPorNivel(partidasComNumero);
  const inicioMataMataPorNivel = primeiraRodadaMataMataPorNivel(partidasComNumero);

  function grupoDaPartida(partida: PartidaItem): { label: string; classes: string; ordem: number } {
    // Partida de fase de grupos (Chave, criada por gerar_fase_de_grupos) --
    // rotula pelo nome da chave, e fica sempre no fim (ordem alta): assim
    // que o mata-mata pos-grupos existe, e ele que importa olhar primeiro.
    if (partida.chave_id != null) {
      const nomeChave = chavePorId.get(partida.chave_id) ?? "Fase de Grupos";
      return { label: nomeChave, classes: CLASSES_FASE_NEUTRA, ordem: 1000 };
    }
    // Formato e por partida (nivel), nao mais um campo unico da modalidade
    // inteira -- uma modalidade pode ter nivel em mata-mata e outro em
    // todos-contra-todos ao mesmo tempo (gerar_chaveamento_confronto). Essa
    // e a liga automatica por contagem (sem chave), continua ordem 0.
    if (partida.formato_chaveamento === "TODOS_CONTRA_TODOS") {
      return { label: "Fase de Grupos", classes: CLASSES_FASE_NEUTRA, ordem: 0 };
    }
    const numero = rodadaPorId.get(partida.rodada_id)?.numero ?? 0;
    if (partida.nivel == null) {
      return { label: `Rodada ${numero}`, classes: CLASSES_FASE_NEUTRA, ordem: -numero };
    }
    const total = totalRodadasPorNivel.get(partida.nivel);
    // numero e o ABSOLUTO da modalidade, mas nomeFase espera o numero
    // RELATIVO ao inicio do mata-mata daquele nivel -- depois de uma fase de
    // grupos, o bracket pode comecar numa rodada != 1 (ex.: grupos usam a
    // rodada 1, mata-mata comeca na 2). Sem isso, um bracket de 1 rodada so
    // que comeca na rodada 2 calcula distancia negativa e cai no fallback
    // generico "Rodada 2" em vez de "Final" (bug real achado testando ao
    // vivo com Cabo de Guerra).
    const inicio = inicioMataMataPorNivel.get(partida.nivel);
    const numeroRelativo = inicio != null ? numero - inicio + 1 : numero;
    // "ordem" tem que ficar numa escala unica (distancia ate a final), senao
    // uma secao sem nome (fallback "Rodada N", bracket grande demais) nao
    // intercala certo com as secoes nomeadas (Oitavas/Quartas/Semi/Final) -
    // regressao ja vista: "Oitavas" ficando depois de "Rodada 1" na tela.
    const distancia = (total ?? 0) - numeroRelativo;
    const fase = nomeFase(numeroRelativo, total);
    if (!fase) {
      return { label: `Rodada ${numero}`, classes: CLASSES_FASE_NEUTRA, ordem: distancia };
    }
    return { label: fase.nome, classes: fase.classes, ordem: distancia };
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
    <main className="mx-auto max-w-3xl p-8">
      <Link
        to={`/eventos/${eventoId}/competicoes?aba=combate`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar para combates
      </Link>
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">
        Pontuar {modalidade!.nome}
      </h1>

      {niveisDisponiveis.length > 1 && (
        <div className="mb-4">
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
            className="w-full max-w-xs rounded border border-slate-300 px-3 py-2"
          >
            <option value="">Todos os niveis</option>
            {niveisDisponiveis.map((nivel) => (
              <option key={nivel} value={nivel}>
                {rotuloNivel(nivel)}
              </option>
            ))}
          </select>
        </div>
      )}

      {todasPartidas.length === 0 && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
          <p>Nenhuma partida gerada ainda: gere o chaveamento/rodadas primeiro.</p>
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
              className={`mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${grupo.classes}`}
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
                    <p className="text-sm text-slate-500">
                      Rodada {rodada?.numero}
                      {partida.nivel != null ? ` · ${rotuloNivel(partida.nivel)}` : ""}
                    </p>
                    <p className="mt-2 text-sm font-medium">
                      <span className={corDaEquipe(partida, partida.equipe_a_id)}>{nomeA}</span>
                      {" vs "}
                      {nomeB ? (
                        <span className={corDaEquipe(partida, partida.equipe_b_id!)}>
                          {nomeB}
                        </span>
                      ) : (
                        <span className="text-slate-400">(bye)</span>
                      )}
                    </p>
                    {partida.status === "EMPATADA" && (
                      <p className="mt-1 text-xs font-medium text-slate-500">Empate</p>
                    )}
                    {partida.status === "ENCERRADA" && partida.vencedor_id && (
                      <p className="mt-1 text-xs font-medium text-emerald-700">
                        Vencedor: {equipePorId.get(partida.vencedor_id) ?? "?"}
                      </p>
                    )}
                  </>
                );

                const linkPartida = `/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${partida.rodada_id}/partidas/${partida.id}/pontuar${nivelFiltro ? `?nivel=${nivelFiltro}` : ""}`;

                if (decidida) {
                  return (
                    <li key={partida.id}>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                        <div className="opacity-80">{corpo}</div>
                        {ehCoordenador && partida.equipe_b_id && (
                          <Link
                            to={linkPartida}
                            className="mt-2 inline-block text-sm font-medium text-slate-700 underline"
                          >
                            Corrigir
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
                      className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-400"
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
