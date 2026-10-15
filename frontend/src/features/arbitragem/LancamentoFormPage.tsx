import { useQuery } from "@tanstack/react-query";
import { useLiveQuery } from "dexie-react-hooks";
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { BarraFixa } from "../../components/BarraFixa";
import { PageHeader } from "../../components/PageHeader";
import { avisarPontuacaoRegistrada } from "../../lib/avisos";
import { db, type LancamentoOutboxItem } from "../../lib/db";
import { derivarLancamentoAtivo, type LancamentoAtivoView } from "../../lib/lancamento-outbox-view";
import { enfileirarConfirmarLancamento, enfileirarCriarLancamento } from "../../lib/outbox";
import { rotuloNivel } from "../../lib/nivel";
import { sincronizar } from "../../lib/sync";
import { CriterioPreview, type CriterioItem, type ValorEstado } from "../ficha/FichaPreviewPage";

interface RodadaInfo {
  id: string;
  modalidade_id: string;
  numero: number;
}

interface ModalidadeInfo {
  id: string;
  nome: string;
  tipo_disputa: string;
  ficha_unica_entre_niveis: boolean;
  tentativas_por_rodada: number;
}

interface PartidaItem {
  id: string;
  equipe_a_id: string;
  equipe_b_id: string | null;
  vencedor_id: string | null;
  status: string;
}

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
  ativo: boolean;
}

interface InscricaoItem {
  id: string;
  equipe_id: string;
  modalidade_id: string;
}

interface FichaResumo {
  id: string;
  nivel: number | null;
  status: string;
}

interface GrupoItem {
  id: string;
  nome: string;
  criterios: CriterioItem[];
}

interface FichaCompleta {
  id: string;
  grupos: GrupoItem[];
}

interface LancamentoResumo {
  id: string;
  equipe_id: string;
  tentativa: number;
  status: string;
  total?: number;
}

export function LancamentoFormPage() {
  const { eventoId, modalidadeId, rodadaId } = useParams<{
    eventoId: string;
    modalidadeId: string;
    rodadaId: string;
  }>();

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const equipeIdPreselecionado = searchParams.get("equipeId");
  const veioPreselecionado = !!equipeIdPreselecionado;
  const partidaIdPreselecionada = searchParams.get("partidaId");
  const partidaVeioPreselecionada = !!partidaIdPreselecionada;
  const voltarParaPontuar = veioPreselecionado || partidaVeioPreselecionada;
  const nivelDaOrigem = searchParams.get("nivel") ?? "";
  const rodadaDaOrigem = searchParams.get("rodada") ?? "";
  const filtrosDaOrigem = new URLSearchParams();
  if (nivelDaOrigem) filtrosDaOrigem.set("nivel", nivelDaOrigem);
  if (rodadaDaOrigem) filtrosDaOrigem.set("rodada", rodadaDaOrigem);
  const destinoPontuar = `/eventos/${eventoId}/modalidades/${modalidadeId}/pontuar${filtrosDaOrigem.toString() ? `?${filtrosDaOrigem.toString()}` : ""}`;

  const [equipeId, setEquipeId] = useState(equipeIdPreselecionado ?? "");
  const [partidaId, setPartidaId] = useState(partidaIdPreselecionada ?? "");
  const [nivelFiltro, setNivelFiltro] = useState("");
  const [tentativa, setTentativa] = useState(() => Number(searchParams.get("tentativa")) || 1);
  const [valores, setValores] = useState<Record<string, ValorEstado>>({});
  const [tempoGastoSeg, setTempoGastoSeg] = useState("");
  const [totalPreview, setTotalPreview] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  const { data: rodada } = useQuery({
    queryKey: ["rodada", rodadaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas/{rodada_id}", {
        params: { path: { rodada_id: rodadaId! } },
      });
      return data as RodadaInfo | undefined;
    },
    enabled: !!rodadaId,
  });

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

  const { data: equipes } = useQuery({
    queryKey: ["equipes", "ativas"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", {
        params: { query: { ativo: true, size: 1000 } },
      });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

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

  const { data: lancamentosDaRodada } = useQuery({
    queryKey: ["lancamentos-da-rodada", rodadaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/lancamentos", {
        params: { query: { rodada_id: rodadaId, size: 200 } },
      });
      return (data?.itens ?? []) as LancamentoResumo[];
    },
    enabled: !!rodadaId,
  });

  const isConfronto = modalidade?.tipo_disputa === "CONFRONTO";

  const { data: partidas } = useQuery({
    queryKey: ["partidas-da-rodada", rodadaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas/{rodada_id}/partidas", {
        params: { path: { rodada_id: rodadaId! } },
      });
      return (data ?? []) as PartidaItem[];
    },
    enabled: !!rodadaId && isConfronto,
  });

  const idsInscritos = new Set((inscricoes ?? []).map((i) => i.equipe_id));
  const idsJaLancadosNaTentativa = new Set(
    (lancamentosDaRodada ?? []).filter((l) => l.tentativa === tentativa).map((l) => l.equipe_id),
  );
  const equipePorId = new Map((equipes ?? []).map((e) => [e.id, e]));

  const partidasAbertas = (partidas ?? []).filter(
    (p) => p.status !== "ENCERRADA" && p.equipe_b_id !== null,
  );
  const partidaSelecionada = (partidas ?? []).find((p) => p.id === partidaId);
  const ladosDaPartida = partidaSelecionada
    ? [partidaSelecionada.equipe_a_id, partidaSelecionada.equipe_b_id]
        .filter((id): id is string => !!id && !idsJaLancadosNaTentativa.has(id))
        .map((id) => equipePorId.get(id))
        .filter((e): e is EquipeItem => !!e)
    : [];

  const equipesElegiveis = isConfronto
    ? ladosDaPartida
    : (equipes ?? [])
        .filter((e) => idsInscritos.has(e.id))
        .filter((e) => !idsJaLancadosNaTentativa.has(e.id))
        .filter((e) => nivelFiltro === "" || e.nivel === Number(nivelFiltro));
  // Nao usa equipesElegiveis aqui: a equipe atualmente selecionada (por
  // preselecao via url ou por ja ter sido escolhida no seletor) precisa
  // continuar carregando a ficha mesmo se ja tiver lancamento pra essa
  // tentativa - e exatamente o caso de retomar um PENDENTE que ficou pra
  // tras (ver lancamentoPendenteExistente).
  const equipeSelecionada = equipePorId.get(equipeId);
  const niveisDisponiveis = Array.from(
    new Set(
      (equipes ?? [])
        .filter((e) => idsInscritos.has(e.id))
        .map((e) => e.nivel),
    ),
  ).sort((a, b) => a - b);

  const fichaId = (() => {
    if (!equipeSelecionada || !modalidade || !fichas) return undefined;
    const ativa = fichas.find(
      (f) =>
        f.status !== "SUBSTITUIDA" &&
        (modalidade.ficha_unica_entre_niveis ? f.nivel === null : f.nivel === equipeSelecionada.nivel),
    );
    return ativa?.id;
  })();

  const { data: ficha } = useQuery({
    queryKey: ["ficha", fichaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas/{ficha_id}", {
        params: { path: { ficha_id: fichaId! } },
      });
      return data as FichaCompleta | undefined;
    },
    enabled: !!fichaId,
  });

  // Fila local (outbox) desta equipe+tentativa: um lancamento vai pra ca
  // imediatamente ao registrar/confirmar, antes de qualquer resposta da
  // rede (contrato offline-first, secao 8 do CLAUDE.md). A tela reflete o
  // estado da fila em tempo real via useLiveQuery.
  const itensDaFila =
    useLiveQuery(
      () =>
        rodadaId && equipeId
          ? db.lancamentoOutbox
              .where("[contexto.rodadaId+contexto.equipeId+contexto.tentativa]")
              .equals([rodadaId, equipeId, tentativa])
              .toArray()
          : Promise.resolve<LancamentoOutboxItem[]>([]),
      [rodadaId, equipeId, tentativa],
    ) ?? [];

  // Se a equipe+tentativa atual ja tem um lancamento PENDENTE vindo do
  // servidor mas nada na fila local desta sessao (ex.: o arbitro registrou
  // em outro momento/dispositivo, ou reabriu o app depois de sincronizar),
  // retoma direto pra confirmacao em vez de deixar tentar "Registrar
  // lancamento" de novo, que o backend recusaria (LANCAMENTO_JA_EXISTE).
  // Cobre tanto PENDENTE quanto CONFIRMADO: sem isso, abrir a ficha direto
  // (link salvo, voltar no navegador, card desatualizado) pra uma equipe que
  // ja tem lancamento confirmado nessa rodada+tentativa mostrava o
  // formulario em branco como se nada tivesse sido lancado ainda - o
  // backend recusa duplicata (409 LANCAMENTO_JA_EXISTE), mas o arbitro via
  // uma tela enganosa antes disso.
  const lancamentoExistente = (lancamentosDaRodada ?? []).find(
    (l) =>
      l.equipe_id === equipeId &&
      l.tentativa === tentativa &&
      (l.status === "PENDENTE" || l.status === "CONFIRMADO"),
  );
  const lancamentoAtivo: LancamentoAtivoView | null =
    derivarLancamentoAtivo({ itensDaFila }) ??
    (lancamentoExistente
      ? {
          id: lancamentoExistente.id,
          lancamentoLocalId: lancamentoExistente.id,
          status: lancamentoExistente.status as "PENDENTE" | "CONFIRMADO",
          total: lancamentoExistente.total ?? 0,
          estadoSincronizacao: "sincronizado",
        }
      : null);

  function rotuloEstadoSincronizacao(view: LancamentoAtivoView): string {
    if (view.status === "CONFIRMADO") return "pontuação enviada e confirmada";
    switch (view.estadoSincronizacao) {
      case "pendente":
        return "na fila — será enviada quando a rede voltar";
      case "enviando":
        return "enviando...";
      case "erro":
        return "erro ao enviar, aguardando nova tentativa";
      default:
        return "pontuação enviada, aguardando confirmação";
    }
  }

  async function simular(novosValores: Record<string, ValorEstado>) {
    if (!fichaId) return;
    const valoresPayload = Object.entries(novosValores).map(([criterio_id, valor]) => ({
      criterio_id,
      ...valor,
    }));
    const { data } = await api.POST("/api/v1/fichas/{ficha_id}/simular", {
      params: { path: { ficha_id: fichaId } },
      body: { valores: valoresPayload } as never,
    });
    setTotalPreview(data?.total ?? null);
  }

  function alterarOcorrencias(criterioId: string, delta: number, max: number | null) {
    const anterior = valores[criterioId]?.ocorrencias ?? 0;
    const proposto = anterior + delta;
    if (proposto < 0) return;
    if (max !== null && proposto > max) return;

    const novosValores = { ...valores, [criterioId]: { ocorrencias: proposto } };
    setValores(novosValores);
    void simular(novosValores);
  }

  function selecionarValorEscala(criterioId: string, valor: number) {
    const novosValores = { ...valores, [criterioId]: { valor } };
    setValores(novosValores);
    void simular(novosValores);
  }

  function alternarModificador(criterioId: string, aplicado: boolean) {
    const novosValores = { ...valores, [criterioId]: { aplicado } };
    setValores(novosValores);
    void simular(novosValores);
  }

  function alternarBooleano(criterioId: string, marcado: boolean) {
    const novosValores = { ...valores, [criterioId]: { ocorrencias: marcado ? 1 : 0 } };
    setValores(novosValores);
    void simular(novosValores);
  }

  async function registrarLancamento() {
    if (!fichaId || !rodadaId || !equipeId || enviando) return;
    setErro(null);
    setEnviando(true);

    const itens = Object.entries(valores).map(([criterio_id, valor]) => ({
      criterio_id,
      ...valor,
    }));

    try {
      // Grava na fila local (outbox) e resolve na hora, sem esperar a rede -
      // e o que resolve o BUG-01 do relatorio: o clique nunca mais fica preso
      // esperando fetch, porque nao ha mais fetch nenhum neste caminho.
      // Desde 14/10/2026 registrar ja confirma no mesmo toque (pedido do
      // coordenador): o CONFIRMAR entra na fila logo atras do CRIAR e o sync
      // so o envia depois que o criar voltar do servidor (dependeDe).
      const { lancamentoLocalId } = await enfileirarCriarLancamento({
        fichaId,
        rodadaId,
        equipeId,
        tentativa,
        itens,
        totalPreview: totalPreview ?? 0,
        partidaId: isConfronto ? partidaId : undefined,
        tempoGastoSeg:
          !isConfronto && tempoGastoSeg !== "" ? Number(tempoGastoSeg) : undefined,
      });
      await enfileirarConfirmarLancamento({ lancamentoLocalId, revision: 1 });
      void sincronizar();
    } catch {
      setErro("Não foi possível registrar o lançamento neste dispositivo. Tente novamente.");
      setEnviando(false);
      return;
    }
    setEnviando(false);
    avisarPontuacaoRegistrada();
    seguirDepoisDeConfirmar();
  }

  async function confirmarLancamento() {
    if (!lancamentoAtivo || confirmando) return;
    setErro(null);
    setConfirmando(true);

    try {
      await enfileirarConfirmarLancamento({
        lancamentoLocalId: lancamentoAtivo.lancamentoLocalId,
        ...(lancamentoAtivo.estadoSincronizacao === "sincronizado"
          ? { lancamentoServidorId: lancamentoAtivo.id }
          : {}),
        revision: 1,
      });
      void sincronizar();
    } catch {
      setErro("Não foi possível confirmar o lançamento neste dispositivo. Tente novamente.");
      setConfirmando(false);
      return;
    }
    setConfirmando(false);
    avisarPontuacaoRegistrada();
    seguirDepoisDeConfirmar();
  }

  function seguirDepoisDeConfirmar() {
    if (voltarParaPontuar) {
      navigate(destinoPontuar);
      return;
    }

    setEquipeId("");
    setPartidaId("");
    setValores({});
    setTotalPreview(null);
  }

  if (
    !rodada ||
    !modalidade ||
    !equipes ||
    !inscricoes ||
    !fichas ||
    !lancamentosDaRodada ||
    (isConfronto && !partidas)
  ) {
    return <main className="px-4 py-6 text-slate-500 sm:p-8">Carregando...</main>;
  }

  const equipeAtual = equipePorId.get(equipeId);

  return (
    <main className="mx-auto max-w-2xl px-4 pb-44 pt-6 sm:px-6">
      <PageHeader
        voltar={{
          para: voltarParaPontuar
            ? destinoPontuar
            : `/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas`,
          rotulo: voltarParaPontuar ? "Voltar para pontuar" : "Voltar para rodadas",
        }}
        sobretitulo={`${modalidade.nome} · Rodada ${rodada.numero}`}
        titulo={veioPreselecionado && equipeAtual ? equipeAtual.nome : "Lançar pontuação"}
      />

      {isConfronto ? (
        partidaVeioPreselecionada ? (
          <p className="mb-6 text-sm text-slate-600">
            Partida:{" "}
            <span className="font-medium text-slate-800">
              {equipePorId.get(partidaSelecionada?.equipe_a_id ?? "")?.nome ?? "?"} vs{" "}
              {equipePorId.get(partidaSelecionada?.equipe_b_id ?? "")?.nome ?? "?"}
            </span>
          </p>
        ) : (
          <div className="mb-6">
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="partida">
              Partida
            </label>
            <select
              id="partida"
              value={partidaId}
              onChange={(e) => {
                setPartidaId(e.target.value);
                setEquipeId("");
              }}
              className="min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2"
            >
              <option value="">Selecione uma partida</option>
              {partidasAbertas.map((partida) => (
                <option key={partida.id} value={partida.id}>
                  {equipePorId.get(partida.equipe_a_id)?.nome ?? "?"} vs{" "}
                  {equipePorId.get(partida.equipe_b_id ?? "")?.nome ?? "?"}
                </option>
              ))}
            </select>
            {partidasAbertas.length === 0 && (
              <p className="mt-1 text-sm text-slate-500">
                Nenhuma partida em aberto nesta rodada.
              </p>
            )}
          </div>
        )
      ) : (
        !veioPreselecionado &&
        niveisDisponiveis.length > 1 && (
          <div className="mb-4">
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="filtro-nivel"
            >
              Filtrar por nivel
            </label>
            <select
              id="filtro-nivel"
              value={nivelFiltro}
              onChange={(e) => setNivelFiltro(e.target.value)}
              className="min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2"
            >
              <option value="">Todos os níveis</option>
              {niveisDisponiveis.map((nivel) => (
                <option key={nivel} value={nivel}>
                  {rotuloNivel(nivel)}
                </option>
              ))}
            </select>
          </div>
        )
      )}

      {veioPreselecionado && equipeAtual && (
        <p className="-mt-3 mb-6 flex flex-wrap gap-1.5">
          <span className="chip border-slate-300 bg-slate-100 text-slate-700">
            {rotuloNivel(equipeAtual.nivel)}
          </span>
          {modalidade.tentativas_por_rodada > 1 && (
            <span className="chip border-neon/40 bg-neon-soft text-neon">{tentativa}ª tentativa</span>
          )}
        </p>
      )}

      {!veioPreselecionado && (!isConfronto || partidaId) && (
        <div className="mb-6">
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="equipe">
            Equipe
          </label>
          <select
            id="equipe"
            value={equipeId}
            onChange={(e) => setEquipeId(e.target.value)}
            className="min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2"
          >
            <option value="">Selecione uma equipe</option>
            {equipesElegiveis.map((equipe) => (
              <option key={equipe.id} value={equipe.id}>
                {equipe.nome} ({rotuloNivel(equipe.nivel)})
              </option>
            ))}
          </select>
          {equipesElegiveis.length === 0 && (
            <p className="mt-1 text-sm text-slate-500">
              Nenhuma equipe pendente de lançamento para esta rodada
              {tentativa > 1 ? ` (tentativa ${tentativa})` : ""}
              {nivelFiltro ? ` no nivel ${nivelFiltro}` : ""}.
            </p>
          )}
        </div>
      )}

      {!veioPreselecionado && modalidade.tentativas_por_rodada > 1 && (
        <div className="mb-6">
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="tentativa">
            Tentativa
          </label>
          <select
            id="tentativa"
            value={tentativa}
            onChange={(e) => setTentativa(Number(e.target.value))}
            className="min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2"
          >
            {Array.from({ length: modalidade.tentativas_por_rodada }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}ª tentativa
              </option>
            ))}
          </select>
        </div>
      )}

      {ficha && (
        <div className="space-y-4">
          {ficha.grupos.map((grupo) => (
            <section key={grupo.id}>
              <h2 className="eyebrow mb-2">{grupo.nome}</h2>
              <div className="space-y-2">
                {grupo.criterios.map((criterio) => (
                  <CriterioPreview
                    key={criterio.id}
                    criterio={criterio}
                    valor={valores[criterio.id]}
                    onIncrementar={() =>
                      alterarOcorrencias(criterio.id, 1, criterio.max_ocorrencias)
                    }
                    onDecrementar={() =>
                      alterarOcorrencias(criterio.id, -1, criterio.max_ocorrencias)
                    }
                    onSelecionarEscala={(valor) => selecionarValorEscala(criterio.id, valor)}
                    onAlternarModificador={(aplicado) =>
                      alternarModificador(criterio.id, aplicado)
                    }
                    onAlternarBooleano={(marcado) => alternarBooleano(criterio.id, marcado)}
                    disabled={!!lancamentoAtivo}
                  />
                ))}
              </div>
            </section>
          ))}

          {!isConfronto && (
            <div>
              <label
                className="mb-1 block text-sm font-medium text-slate-700"
                htmlFor="tempo-gasto-seg"
              >
                Tempo gasto (segundos) <span className="text-slate-500">— opcional</span>
              </label>
              <input
                id="tempo-gasto-seg"
                type="number"
                inputMode="numeric"
                min={0}
                value={tempoGastoSeg}
                onChange={(e) => setTempoGastoSeg(e.target.value)}
                disabled={!!lancamentoAtivo}
                className="min-h-12 w-36 rounded-lg border border-slate-300 px-3 py-2 text-lg disabled:opacity-50"
              />
            </div>
          )}


          {erro && (
            <Aviso tipo="erro">
              <p>{erro}</p>
            </Aviso>
          )}

          {!lancamentoAtivo && (
            <BarraFixa>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Prévia da nota
                </p>
                <p className="font-display text-4xl font-bold leading-none text-neon">
                  {totalPreview ?? 0}
                </p>
              </div>
              <button
                type="button"
                onClick={registrarLancamento}
                disabled={enviando}
                className="btn-primary min-h-14 flex-1 text-base sm:flex-none sm:px-8"
              >
                {enviando ? "Enviando..." : "Registrar lançamento"}
              </button>
            </BarraFixa>
          )}

          {lancamentoAtivo && lancamentoAtivo.estadoSincronizacao === "conflito" && (
            <Aviso tipo="erro">
              <p className="text-sm font-semibold text-red-800">
                Conflito ao sincronizar este lançamento
              </p>
              <p className="mt-1 text-sm text-red-700">{lancamentoAtivo.conflito?.mensagem}</p>
              <p className="mt-2 text-sm text-red-700">
                O lançamento não foi sobrescrito. Fale com a secretaria ou a coordenação antes de
                tentar novamente.
              </p>
            </Aviso>
          )}

          {lancamentoAtivo && lancamentoAtivo.estadoSincronizacao !== "conflito" && (
            <BarraFixa
              tom={
                lancamentoAtivo.status === "CONFIRMADO"
                  ? "sucesso"
                  : lancamentoAtivo.estadoSincronizacao === "pendente" ||
                      lancamentoAtivo.estadoSincronizacao === "enviando"
                    ? "aviso"
                    : "neutro"
              }
            >
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-slate-600">
                  {lancamentoAtivo.status === "CONFIRMADO" && (
                    <span className="mr-1 text-emerald-700" aria-hidden="true">
                      ✓
                    </span>
                  )}
                  Nota registrada — {rotuloEstadoSincronizacao(lancamentoAtivo)}
                </p>
                <p className="font-display text-4xl font-bold leading-none text-slate-900">
                  {lancamentoAtivo.total}
                </p>
                <p className="sr-only">Status: {lancamentoAtivo.status}</p>
              </div>
              {lancamentoAtivo.status === "PENDENTE" && (
                <button
                  type="button"
                  onClick={confirmarLancamento}
                  disabled={confirmando}
                  className="btn-success min-h-14 flex-1 text-base sm:flex-none sm:px-8"
                >
                  {confirmando ? "Confirmando..." : "✓ Confirmar lançamento"}
                </button>
              )}
            </BarraFixa>
          )}
        </div>
      )}
    </main>
  );
}
