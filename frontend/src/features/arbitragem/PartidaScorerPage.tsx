import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

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
  decisao_partida: string;
}

interface FichaResumo {
  id: string;
  nivel: number | null;
  status: string;
}

interface CriterioItem {
  id: string;
  nome: string;
  categoria: string;
  tipo: string;
  valores_permitidos: number[] | null;
  max_ocorrencias: number | null;
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
  id: string;
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
  "Resultado do combate": { 1: "Waza-ari", 2: "Ippon" },
};

function rotuloEscala(nomeCriterio: string, valor: number): string {
  return ROTULOS_ESCALA[nomeCriterio]?.[valor] ?? String(valor);
}

function suportaScorerInline(criterios: CriterioItem[]): boolean {
  return (
    criterios.length > 1 &&
    criterios.every((c) => c.tipo === "BOOLEANO" || c.tipo === "CONTADOR")
  );
}

function corCriterio(categoria: string, pressed: boolean): string {
  const ePenalidade = categoria === "PENALIDADE";
  if (pressed) {
    return ePenalidade
      ? "border-red-500 bg-red-50 text-red-800"
      : "border-emerald-500 bg-emerald-50 text-emerald-800";
  }
  return ePenalidade
    ? "border-red-200 text-slate-800 hover:border-red-400 hover:bg-red-50"
    : "border-emerald-200 text-slate-800 hover:border-emerald-400 hover:bg-emerald-50";
}

function ColunaEquipeMultiCriterio({
  criterios,
  nome,
  estado,
  desabilitado,
  onAlterar,
  onAlternar,
}: {
  criterios: CriterioItem[];
  nome: string;
  estado: Record<string, number>;
  desabilitado: boolean;
  onAlterar: (criterioId: string, delta: number, max: number | null) => void;
  onAlternar: (criterioId: string) => void;
}) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold text-slate-700">{nome}</p>
      <div className="flex flex-col gap-2">
        {criterios.map((criterio) =>
          criterio.tipo === "BOOLEANO" ? (
            <button
              key={criterio.id}
              type="button"
              disabled={desabilitado}
              aria-pressed={!!estado[criterio.id]}
              onClick={() => onAlternar(criterio.id)}
              className={`min-h-12 w-full rounded border px-3 py-2 text-left text-sm font-medium disabled:opacity-50 ${corCriterio(
                criterio.categoria,
                !!estado[criterio.id],
              )}`}
            >
              {criterio.nome}
            </button>
          ) : (
            <div
              key={criterio.id}
              className={`flex min-h-12 w-full items-center gap-2 rounded border px-2 py-1 ${corCriterio(
                criterio.categoria,
                false,
              )}`}
            >
              <span className="flex-1 text-sm text-slate-800">{criterio.nome}</span>
              <button
                type="button"
                disabled={desabilitado}
                aria-label={`Diminuir ${criterio.nome} - ${nome}`}
                onClick={() => onAlterar(criterio.id, -1, criterio.max_ocorrencias)}
                className="flex h-8 w-8 items-center justify-center rounded border border-slate-300 bg-white text-lg leading-none disabled:opacity-50"
              >
                −
              </button>
              <span className="w-4 text-center text-sm font-semibold">
                {estado[criterio.id] ?? 0}
              </span>
              <button
                type="button"
                disabled={desabilitado}
                aria-label={`Aumentar ${criterio.nome} - ${nome}`}
                onClick={() => onAlterar(criterio.id, 1, criterio.max_ocorrencias)}
                className="flex h-8 w-8 items-center justify-center rounded border border-slate-300 bg-white text-lg leading-none disabled:opacity-50"
              >
                +
              </button>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

function MultiCriterioScorer({
  criterios,
  nomeA,
  nomeB,
  desabilitado,
  onRegistrar,
}: {
  criterios: CriterioItem[];
  nomeA: string;
  nomeB: string | null;
  desabilitado: boolean;
  onRegistrar: (itensA: ItemEnvio[], itensB: ItemEnvio[]) => void;
}) {
  const [estadoA, setEstadoA] = useState<Record<string, number>>({});
  const [estadoB, setEstadoB] = useState<Record<string, number>>({});

  function alterar(
    lado: "A" | "B",
    criterioId: string,
    delta: number,
    max: number | null,
  ) {
    const setEstado = lado === "A" ? setEstadoA : setEstadoB;
    setEstado((atual) => {
      const valorAtual = atual[criterioId] ?? 0;
      let proximo = valorAtual + delta;
      if (proximo < 0) proximo = 0;
      if (max !== null && proximo > max) proximo = max;
      return { ...atual, [criterioId]: proximo };
    });
  }

  function alternar(lado: "A" | "B", criterioId: string) {
    const setEstado = lado === "A" ? setEstadoA : setEstadoB;
    const setEstadoOposto = lado === "A" ? setEstadoB : setEstadoA;

    setEstado((atual) => {
      const ligando = !atual[criterioId];
      // Um combate so tem um "vencedor"/"violador" por criterio: marcar pra
      // um lado desmarca automaticamente do outro, ja que fisicamente nao da
      // pra acontecer a mesma coisa (ex.: "Carro que ficou na frente") pras
      // duas equipes ao mesmo tempo. So se aplica a criterio BOOLEANO (essa
      // funcao nunca e chamada pra CONTADOR) - "Evitar a colisao" continua
      // independente por equipe.
      if (ligando) {
        setEstadoOposto((atualOposto) =>
          atualOposto[criterioId] ? { ...atualOposto, [criterioId]: 0 } : atualOposto,
        );
      }
      return { ...atual, [criterioId]: ligando ? 1 : 0 };
    });
  }

  function itensDe(estado: Record<string, number>): ItemEnvio[] {
    return Object.entries(estado)
      .filter(([, ocorrencias]) => ocorrencias > 0)
      .map(([criterio_id, ocorrencias]) => ({ criterio_id, ocorrencias }));
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <ColunaEquipeMultiCriterio
          criterios={criterios}
          nome={nomeA}
          estado={estadoA}
          desabilitado={desabilitado}
          onAlterar={(criterioId, delta, max) => alterar("A", criterioId, delta, max)}
          onAlternar={(criterioId) => alternar("A", criterioId)}
        />
        {nomeB && (
          <ColunaEquipeMultiCriterio
            criterios={criterios}
            nome={nomeB}
            estado={estadoB}
            desabilitado={desabilitado}
            onAlterar={(criterioId, delta, max) => alterar("B", criterioId, delta, max)}
            onAlternar={(criterioId) => alternar("B", criterioId)}
          />
        )}
      </div>
      <button
        type="button"
        disabled={desabilitado}
        onClick={() => onRegistrar(itensDe(estadoA), itensDe(estadoB))}
        className="min-h-12 rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        Registrar
      </button>
    </div>
  );
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
  const [searchParams] = useSearchParams();
  const nivelFiltro = searchParams.get("nivel") ?? "";

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

  function lancamentoExistente(equipeId: string, tentativa: number) {
    return lancamentosDaPartida.find(
      (l) => l.equipe_id === equipeId && l.tentativa === tentativa,
    );
  }

  function lancamentoConfirmado(equipeId: string, tentativa: number) {
    const existente = lancamentoExistente(equipeId, tentativa);
    return existente?.status === "CONFIRMADO" ? existente : undefined;
  }

  const criterios = ficha?.grupos.flatMap((g) => g.criterios) ?? [];
  const criterioUnico = criterios.length === 1 ? criterios[0] : undefined;
  const valoresOrdenados = [...(criterioUnico?.valores_permitidos ?? [])].sort((a, b) => a - b);

  const tentativasArr = modalidade
    ? Array.from({ length: modalidade.tentativas_por_rodada }, (_, i) => i + 1)
    : [];

  const usaSomaPontos = modalidade?.decisao_partida === "SOMA_PONTOS";

  let empateTecnico = false;
  let empatouNoDesempate = false;
  const tentativaDesempate = tentativasArr.length + 1;
  if (partida?.status === "AGENDADA" && partida.equipe_b_id) {
    let vitoriasA = 0;
    let vitoriasB = 0;
    let somaA = 0;
    let somaB = 0;
    let todasDecididas = true;
    for (const t of tentativasArr) {
      const lancA = lancamentoConfirmado(partida.equipe_a_id, t);
      const lancB = lancamentoConfirmado(partida.equipe_b_id, t);
      if (!lancA || !lancB) {
        todasDecididas = false;
        break;
      }
      somaA += lancA.total;
      somaB += lancB.total;
      if (lancA.total > lancB.total) vitoriasA += 1;
      else if (lancB.total > lancA.total) vitoriasB += 1;
    }
    // Mesma regra do backend (registrar_resultado_lancamento): com
    // decisao_partida=SOMA_PONTOS quem decide a partida e o total somado dos
    // combates, nao quantos combates cada equipe venceu - o empate tecnico
    // (que libera o combate extra) precisa usar o mesmo criterio, senao o
    // banner pode nao aparecer quando o backend genuinamente precisa do
    // desempate, ou aparecer quando o backend ja decidiu pela soma.
    empateTecnico = todasDecididas && (usaSomaPontos ? somaA === somaB : vitoriasA === vitoriasB);

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
      // Reaproveita o que ja existe pra essa equipe+tentativa em vez de tentar
      // criar de novo: um retry apos falha parcial (ex.: confirmar caiu por
      // causa de rede ruim no ginasio) nao pode tentar recriar um lancamento
      // que ja foi criado ou ja foi confirmado - o backend recusa duplicata
      // (LANCAMENTO_JA_EXISTE) e sem isso o retry ficava travado pra sempre.
      const existente = lancamentoExistente(lado.equipeId, tentativa);
      if (existente?.status === "CONFIRMADO") continue;

      let lancamentoId = existente?.id;
      if (!lancamentoId) {
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
        await queryClient.invalidateQueries({ queryKey: ["lancamentos-da-rodada", rodadaId] });
        if (error || !data) {
          setErro(extrairErro(error).mensagem);
          setEnviando(null);
          return;
        }
        lancamentoId = (data as { id: string }).id;
      }

      const { error: erroConfirmar } = await api.POST(
        "/api/v1/lancamentos/{lancamento_id}/confirmar",
        { params: { path: { lancamento_id: lancamentoId } } },
      );
      await queryClient.invalidateQueries({ queryKey: ["lancamentos-da-rodada", rodadaId] });
      if (erroConfirmar) {
        setErro(extrairErro(erroConfirmar).mensagem);
        setEnviando(null);
        return;
      }
    }

    setEnviando(null);
    await queryClient.invalidateQueries({ queryKey: ["partidas-da-rodada", rodadaId] });

    const partidasAtualizadas = queryClient.getQueryData<PartidaItem[]>([
      "partidas-da-rodada",
      rodadaId,
    ]);
    const partidaAtual = partidasAtualizadas?.find((p) => p.id === partidaId);
    if (partidaAtual && (partidaAtual.status === "ENCERRADA" || partidaAtual.status === "EMPATADA")) {
      // Partida decidida: volta direto pra lista de Pontuar, sem precisar de
      // clique - agiliza lancar varias partidas seguidas (ex.: bracket
      // grande, dezenas de partidas na mesma rodada). Preserva o filtro de
      // nivel que estava ativo, senao a lista volta sempre pra "todos os
      // niveis" e atrapalha quem esta pontuando so um nivel de cada vez.
      navigate(
        `/eventos/${eventoId}/modalidades/${modalidadeId}/pontuar${nivelFiltro ? `?nivel=${nivelFiltro}` : ""}`,
      );
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

  function enviarMultiCriterio(tentativa: number, itensA: ItemEnvio[], itensB: ItemEnvio[]) {
    if (!partida) return;
    void enviarCombate(tentativa, [
      { equipeId: partida.equipe_a_id, itens: itensA },
      ...(partida.equipe_b_id ? [{ equipeId: partida.equipe_b_id, itens: itensB }] : []),
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
        to={`/eventos/${eventoId}/modalidades/${modalidadeId}/pontuar${nivelFiltro ? `?nivel=${nivelFiltro}` : ""}`}
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
          {usaSomaPontos
            ? "Empate na soma dos pontos — decida com o combate extra de desempate abaixo."
            : "Empate na contagem de combates — decida com o combate extra de desempate abaixo."}
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
                    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                      <div>
                        <p className="mb-1 text-xs text-slate-600">{nomeA}</p>
                        <div className="flex flex-col gap-2">
                          {valoresNaoZero.map((v) => (
                            <button
                              key={v}
                              type="button"
                              disabled={enviando === tentativa}
                              onClick={() => enviarEscala(tentativa, "A", v)}
                              className="min-h-12 w-full rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
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
                          className="min-h-12 rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 disabled:opacity-50"
                        >
                          Empate
                        </button>
                      )}
                      <div>
                        <p className="mb-1 text-xs text-slate-600">{nomeB}</p>
                        <div className="flex flex-col gap-2">
                          {valoresNaoZero.map((v) => (
                            <button
                              key={v}
                              type="button"
                              disabled={enviando === tentativa}
                              onClick={() => enviarEscala(tentativa, "B", v)}
                              className="min-h-12 w-full rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                            >
                              {rotuloEscala(criterioUnico.nome, v)}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : suportaScorerInline(criterios) ? (
                  <MultiCriterioScorer
                    criterios={criterios}
                    nomeA={nomeA}
                    nomeB={nomeB}
                    desabilitado={enviando === tentativa}
                    onRegistrar={(itensA, itensB) =>
                      enviarMultiCriterio(tentativa, itensA, itensB)
                    }
                  />
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
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="mb-1 text-xs text-slate-600">{nomeA}</p>
                    <div className="flex flex-col gap-2">
                      {valoresNaoZero.map((v) => (
                        <button
                          key={v}
                          type="button"
                          disabled={enviando === tentativaDesempate}
                          onClick={() => enviarEscala(tentativaDesempate, "A", v)}
                          className="min-h-12 w-full rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                        >
                          {rotuloEscala(criterioUnico.nome, v)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-xs text-slate-600">{nomeB}</p>
                    <div className="flex flex-col gap-2">
                      {valoresNaoZero.map((v) => (
                        <button
                          key={v}
                          type="button"
                          disabled={enviando === tentativaDesempate}
                          onClick={() => enviarEscala(tentativaDesempate, "B", v)}
                          className="min-h-12 w-full rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:border-emerald-400 hover:bg-emerald-50 disabled:opacity-50"
                        >
                          {rotuloEscala(criterioUnico.nome, v)}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : suportaScorerInline(criterios) ? (
                <MultiCriterioScorer
                  criterios={criterios}
                  nomeA={nomeA}
                  nomeB={nomeB}
                  desabilitado={enviando === tentativaDesempate}
                  onRegistrar={(itensA, itensB) =>
                    enviarMultiCriterio(tentativaDesempate, itensA, itensB)
                  }
                />
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
