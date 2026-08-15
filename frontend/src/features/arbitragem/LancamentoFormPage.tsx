import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
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

interface LancamentoResultado {
  id: string;
  status: string;
  total: number;
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

  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const equipeIdPreselecionado = searchParams.get("equipeId");
  const veioPreselecionado = !!equipeIdPreselecionado;
  const partidaIdPreselecionada = searchParams.get("partidaId");
  const partidaVeioPreselecionada = !!partidaIdPreselecionada;
  const voltarParaPontuar = veioPreselecionado || partidaVeioPreselecionada;
  const nivelDaOrigem = searchParams.get("nivel") ?? "";
  const destinoPontuar = `/eventos/${eventoId}/modalidades/${modalidadeId}/pontuar${nivelDaOrigem ? `?nivel=${nivelDaOrigem}` : ""}`;

  const [equipeId, setEquipeId] = useState(equipeIdPreselecionado ?? "");
  const [partidaId, setPartidaId] = useState(partidaIdPreselecionada ?? "");
  const [nivelFiltro, setNivelFiltro] = useState("");
  const [tentativa, setTentativa] = useState(() => Number(searchParams.get("tentativa")) || 1);
  const [valores, setValores] = useState<Record<string, ValorEstado>>({});
  const [totalPreview, setTotalPreview] = useState<number | null>(null);
  const [lancamento, setLancamento] = useState<LancamentoResultado | null>(null);
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
        params: { query: { ativo: true, size: 200 } },
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

  // Se a equipe+tentativa atual ja tem um lancamento PENDENTE (ex.: o
  // arbitro registrou, saiu da tela antes de confirmar - "← Voltar" perde o
  // estado local - e reabriu o mesmo card depois), retoma direto pra
  // confirmacao em vez de deixar tentar "Registrar lancamento" de novo, que
  // o backend recusaria (LANCAMENTO_JA_EXISTE).
  const lancamentoPendenteExistente = (lancamentosDaRodada ?? []).find(
    (l) => l.equipe_id === equipeId && l.tentativa === tentativa && l.status === "PENDENTE",
  );
  const lancamentoAtivo: LancamentoResultado | null =
    lancamento ??
    (lancamentoPendenteExistente
      ? {
          id: lancamentoPendenteExistente.id,
          status: lancamentoPendenteExistente.status,
          total: lancamentoPendenteExistente.total ?? 0,
        }
      : null);

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
    if (!fichaId || !rodadaId || !equipeId) return;
    setErro(null);
    setEnviando(true);

    const itens = Object.entries(valores).map(([criterio_id, valor]) => ({
      criterio_id,
      ...valor,
    }));

    const { data, error } = await api.POST("/api/v1/lancamentos", {
      body: {
        ficha_id: fichaId,
        rodada_id: rodadaId,
        tentativa,
        equipe_id: equipeId,
        ...(isConfronto ? { partida_id: partidaId } : {}),
        client_operation_id: crypto.randomUUID(),
        itens,
      } as never,
    });

    await queryClient.invalidateQueries({ queryKey: ["lancamentos-da-rodada", rodadaId] });
    setEnviando(false);
    if (error || !data) {
      setErro(extrairErro(error).mensagem);
      return;
    }

    setLancamento(data as LancamentoResultado);
  }

  async function confirmarLancamento() {
    if (!lancamentoAtivo) return;
    setErro(null);
    setConfirmando(true);
    const { data, error } = await api.POST("/api/v1/lancamentos/{lancamento_id}/confirmar", {
      params: { path: { lancamento_id: lancamentoAtivo.id } },
    });
    setConfirmando(false);

    if (error || !data) {
      setErro(extrairErro(error).mensagem);
      return;
    }

    await queryClient.invalidateQueries({ queryKey: ["lancamentos-da-rodada", rodadaId] });
    await queryClient.invalidateQueries({ queryKey: ["partidas-da-rodada", rodadaId] });

    if (voltarParaPontuar) {
      navigate(destinoPontuar);
      return;
    }

    setEquipeId("");
    setPartidaId("");
    setValores({});
    setTotalPreview(null);
    setLancamento(null);
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
    return <main className="p-8 text-slate-500">Carregando...</main>;
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <Link
        to={
          voltarParaPontuar
            ? destinoPontuar
            : `/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas`
        }
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar {voltarParaPontuar ? "para pontuar" : "para rodadas"}
      </Link>
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">
        Lancar pontuacao — Rodada {rodada.numero}
      </h1>

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
              className="w-full rounded border border-slate-300 px-3 py-2"
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
              className="w-full rounded border border-slate-300 px-3 py-2"
            >
              <option value="">Todos os niveis</option>
              {niveisDisponiveis.map((nivel) => (
                <option key={nivel} value={nivel}>
                  Nivel {nivel}
                </option>
              ))}
            </select>
          </div>
        )
      )}

      {veioPreselecionado && equipePorId.get(equipeId) && (
        <p className="mb-6 text-sm text-slate-600">
          Pontuando: <span className="font-medium text-slate-800">{equipePorId.get(equipeId)!.nome}</span>{" "}
          (Nivel {equipePorId.get(equipeId)!.nivel})
          {modalidade.tentativas_por_rodada > 1 ? ` · ${tentativa}ª tentativa` : ""}
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
            className="w-full rounded border border-slate-300 px-3 py-2"
          >
            <option value="">Selecione uma equipe</option>
            {equipesElegiveis.map((equipe) => (
              <option key={equipe.id} value={equipe.id}>
                {equipe.nome} (Nivel {equipe.nivel})
              </option>
            ))}
          </select>
          {equipesElegiveis.length === 0 && (
            <p className="mt-1 text-sm text-slate-500">
              Nenhuma equipe pendente de lancamento para esta rodada
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
            className="w-full rounded border border-slate-300 px-3 py-2"
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
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
                {grupo.nome}
              </h2>
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
                  />
                ))}
              </div>
            </section>
          ))}

          <p className="text-sm text-slate-500">
            Preview: <span className="font-semibold text-slate-800">{totalPreview ?? 0}</span>
          </p>

          {erro && (
            <div className="flex items-start gap-2 rounded border border-red-200 bg-red-50 p-3">
              <span className="text-lg leading-none text-red-600" aria-hidden="true">
                ⚠
              </span>
              <p className="text-sm text-red-700">{erro}</p>
            </div>
          )}

          {!lancamentoAtivo && (
            <button
              type="button"
              onClick={registrarLancamento}
              disabled={enviando}
              className="rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50"
            >
              {enviando ? "Enviando..." : "Registrar lancamento"}
            </button>
          )}

          {lancamentoAtivo && (
            <div
              className={`rounded border p-4 ${
                lancamentoAtivo.status === "CONFIRMADO"
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <p className="text-sm text-slate-500">
                {lancamentoAtivo.status === "CONFIRMADO" && (
                  <span className="mr-1 text-emerald-700" aria-hidden="true">
                    ✓
                  </span>
                )}
                Total persistido —{" "}
                {lancamentoAtivo.status === "CONFIRMADO"
                  ? "pontuação enviada e confirmada"
                  : "pontuação enviada, aguardando confirmação"}
              </p>
              <p className="text-3xl font-bold text-slate-900">{lancamentoAtivo.total}</p>
              <p className="mt-1 text-sm text-slate-600">Status: {lancamentoAtivo.status}</p>
              {lancamentoAtivo.status === "PENDENTE" && (
                <button
                  type="button"
                  onClick={confirmarLancamento}
                  disabled={confirmando}
                  className="mt-3 rounded bg-emerald-700 px-4 py-2 font-medium text-white disabled:opacity-50"
                >
                  {confirmando ? "Confirmando..." : "Confirmar lancamento"}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
