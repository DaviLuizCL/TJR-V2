import { useQueries, useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { PageHeader } from "../../components/PageHeader";
import { iconeModalidade } from "../../lib/modalidade-icone";
import { rotuloNivel } from "../../lib/nivel";

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
  ordem_apresentacao?: number | null;
}

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
  // Ausente (marcado pela coordenacao) vai pro fim da fila, mas segue clicavel.
  presente?: boolean;
}

interface LancamentoResumo {
  equipe_id: string;
  tentativa: number;
  status: string;
}

interface Pendencia {
  equipe: EquipeItem;
  rodada: RodadaItem;
  tentativa: number;
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
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const nivelFiltro = searchParams.get("nivel") ?? "";
  const rodadaFiltro = searchParams.get("rodada") ?? "";

  function atualizarFiltro(chave: "nivel" | "rodada", valor: string) {
    const novo = new URLSearchParams(searchParams);
    if (valor) novo.set(chave, valor);
    else novo.delete(chave);
    setSearchParams(novo);
  }

  const idsInscritos = new Set((inscricoes ?? []).map((i) => i.equipe_id));
  // Sequencia de competicao sorteada pelo coordenador (mesma pra todas as
  // rodadas). Arena nao existe mais: a equipe vai pra arena que estiver livre.
  const ordemPorEquipe = new Map(
    (inscricoes ?? []).map((i) => [i.equipe_id, i.ordem_apresentacao ?? null]),
  );
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

  const tentativasPorRodada = modalidade?.tentativas_por_rodada ?? 1;

  function proximaPendencia(equipeId: string): { rodada: RodadaItem; tentativa: number } | null {
    for (const rodada of rodadasOrdenadas) {
      const lancamentosDaRodada = lancamentosPorRodada.get(rodada.id) ?? [];
      for (let tentativa = 1; tentativa <= tentativasPorRodada; tentativa++) {
        // Anulado nao conta: o coordenador anulou pra equipe refazer.
        const jaTem = lancamentosDaRodada.some(
          (l) => l.equipe_id === equipeId && l.tentativa === tentativa && l.status !== "ANULADO",
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
    const ausenteA = a.equipe.presente === false;
    const ausenteB = b.equipe.presente === false;
    if (ausenteA !== ausenteB) return Number(ausenteA) - Number(ausenteB);
    if (a.rodada.numero !== b.rodada.numero) return a.rodada.numero - b.rodada.numero;
    if (a.tentativa !== b.tentativa) return a.tentativa - b.tentativa;
    const ordemA = ordemPorEquipe.get(a.equipe.id) ?? Number.POSITIVE_INFINITY;
    const ordemB = ordemPorEquipe.get(b.equipe.id) ?? Number.POSITIVE_INFINITY;
    if (ordemA !== ordemB) return ordemA - ordemB;
    return a.equipe.nome.localeCompare(b.equipe.nome);
  });

  const pendenciasExibidas = pendencias.filter(
    (p) => rodadaFiltro === "" || p.rodada.numero === Number(rodadaFiltro),
  );

  const carregando =
    !modalidade || !rodadas || !inscricoes || !equipesTodas || lancamentosQueries.some((q) => q.isLoading);

  if (carregando) {
    return (
      <main className="px-4 py-6 sm:p-8">
        <p className="animate-pulse text-slate-500">Carregando...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        voltar={{
          para: `/eventos/${eventoId}/competicoes?aba=individual&sub=pontuar`,
          rotulo: "Voltar para pontuar",
        }}
        sobretitulo="Pontuar"
        titulo={
          <>
            <span aria-hidden="true">{iconeModalidade(modalidade.nome)} </span>
            {modalidade.nome}
          </>
        }
        descricao="Toque na equipe que vai se apresentar agora. A primeira da lista é a próxima da fila."
      />

      {(niveisDisponiveis.length > 1 || rodadasOrdenadas.length > 1) && (
        <div className="card mb-6 grid grid-cols-2 gap-3 p-4 sm:flex sm:flex-wrap sm:gap-4">
          {niveisDisponiveis.length > 1 && (
            <div>
              <label
                className="mb-1 block text-sm font-medium text-slate-700"
                htmlFor="filtro-nivel"
              >
                Filtrar por nivel
              </label>
              <select
                id="filtro-nivel"
                value={nivelFiltro}
                onChange={(e) => atualizarFiltro("nivel", e.target.value)}
                className="min-h-12 w-full max-w-xs rounded-lg sm:min-w-[12rem] border border-slate-300 px-3 py-2"
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

          {rodadasOrdenadas.length > 1 && (
            <div>
              <label
                className="mb-1 block text-sm font-medium text-slate-700"
                htmlFor="filtro-rodada"
              >
                Filtrar por rodada
              </label>
              <select
                id="filtro-rodada"
                value={rodadaFiltro}
                onChange={(e) => atualizarFiltro("rodada", e.target.value)}
                className="min-h-12 w-full max-w-xs rounded-lg sm:min-w-[12rem] border border-slate-300 px-3 py-2"
              >
                <option value="">Todas as rodadas</option>
                {rodadasOrdenadas.map((rodada) => (
                  <option key={rodada.id} value={rodada.numero}>
                    Rodada {rodada.numero}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {pendencias.length === 0 && equipesFiltradas.length === 0 && (
        <div className="card p-5 text-slate-600">
          <p>
            <span aria-hidden="true">📭 </span>Nenhuma equipe pendente: a modalidade ainda não tem equipe
            inscrita. A coordenação inscreve as equipes em Equipes → Editar.
          </p>
        </div>
      )}

      {pendencias.length === 0 && equipesFiltradas.length > 0 && rodadasOrdenadas.length === 0 && (
        <Aviso tipo="alerta">
          <p>
            Nenhuma rodada foi criada para esta modalidade. Gere as
            rodadas antes de pontuar.
          </p>
          <Link
            to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas`}
            className="btn mt-3 bg-amber-500 text-slate-50"
          >
            Gerar rodadas →
          </Link>
        </Aviso>
      )}

      {pendencias.length === 0 && equipesFiltradas.length > 0 && rodadasOrdenadas.length > 0 && (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-6 text-center text-emerald-800">
          <p className="text-4xl" aria-hidden="true">🏁</p>
          <p className="mt-2 font-display text-xl font-bold">Tudo pontuado!</p>
          <p className="text-sm">Nenhuma equipe pendente: todas já completaram todas as rodadas.</p>
        </div>
      )}

      {pendencias.length > 0 && pendenciasExibidas.length === 0 && (
        <p className="card p-5 text-slate-500">Nenhuma equipe pendente na rodada selecionada.</p>
      )}

      <ul className="grid gap-3 sm:grid-cols-2">
        {pendenciasExibidas.map(({ equipe, rodada, tentativa }, indice) => {
          const ordem = ordemPorEquipe.get(equipe.id);
          const ausente = equipe.presente === false;
          const proxima = indice === 0 && !ausente;
          const aguardandoConfirmacao = temLancamentoPendente(equipe.id);

          return (
            <li key={equipe.id} className={proxima ? "sm:col-span-2" : undefined}>
              <Link
                to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas/${rodada.id}/lancamentos/novo?equipeId=${equipe.id}&tentativa=${tentativa}${nivelFiltro ? `&nivel=${nivelFiltro}` : ""}${rodadaFiltro ? `&rodada=${rodadaFiltro}` : ""}`}
                className={`card group flex min-h-[88px] items-center gap-4 p-4 hover:border-neon/60 ${
                  proxima ? "border-neon/50 shadow-glow" : ""
                } ${ausente ? "opacity-60" : ""}`}
              >
                <span
                  aria-hidden="true"
                  className={`grid h-14 w-14 shrink-0 place-items-center rounded-xl font-display font-bold ${
                    ordem ? "text-2xl" : "text-xs uppercase"
                  } ${proxima ? "bg-neon text-slate-50" : "bg-slate-100 text-slate-600 ring-1 ring-slate-200"}`}
                >
                  {ordem ?? `R${rodada.numero}`}
                </span>
                <div className="min-w-0 flex-1">
                  {proxima && <p className="eyebrow mb-0.5">Próxima</p>}
                  <h2 className="truncate font-display text-xl font-bold text-slate-900">
                    {equipe.nome}
                  </h2>
                  <p className="text-sm text-slate-500">
                    {rotuloNivel(equipe.nivel)}
                    {ordem ? ` · ${ordem}º na sequência` : ""}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <span className="chip border-slate-300 bg-slate-100 text-slate-700">
                      Rodada {rodada.numero}
                      {tentativasPorRodada > 1 ? ` · Tentativa ${tentativa}` : ""}
                    </span>
                    {ausente && (
                      <span className="chip border-red-300 bg-red-50 text-red-700">Ausente</span>
                    )}
                    {aguardandoConfirmacao && (
                      <span className="chip border-amber-300 bg-amber-50 text-amber-800">
                        ⚠ Pendente de confirmação
                      </span>
                    )}
                  </div>
                </div>
                <span
                  aria-hidden="true"
                  className="font-display text-2xl text-slate-400 group-hover:translate-x-1 group-hover:text-neon"
                >
                  →
                </span>
              </Link>
            </li>
          );
        })}
      </ul>

      {completas.length > 0 && rodadasOrdenadas.length > 0 && (
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
