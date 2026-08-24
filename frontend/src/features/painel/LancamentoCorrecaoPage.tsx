import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { CriterioPreview, type CriterioItem, type ValorEstado } from "../ficha/FichaPreviewPage";

interface ItemLancamento {
  criterio_id: string | null;
  criterio_snapshot: { tipo?: string; aplicado?: boolean };
  ocorrencias: number | null;
  valor: number | null;
}

interface LancamentoDetalhe {
  id: string;
  ficha_id: string;
  revision: number;
  status: string;
  total: number;
  itens: ItemLancamento[];
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

export function LancamentoCorrecaoPage() {
  const { lancamentoId } = useParams<{ lancamentoId: string }>();
  const navigate = useNavigate();

  const [valores, setValores] = useState<Record<string, ValorEstado>>({});
  const [inicializado, setInicializado] = useState(false);
  const [justificativa, setJustificativa] = useState("");
  const [totalPreview, setTotalPreview] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const { data: lancamento } = useQuery({
    queryKey: ["lancamento", lancamentoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/lancamentos/{lancamento_id}", {
        params: { path: { lancamento_id: lancamentoId! } },
      });
      return data as LancamentoDetalhe | undefined;
    },
    enabled: !!lancamentoId,
  });

  const { data: ficha } = useQuery({
    queryKey: ["ficha", lancamento?.ficha_id],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas/{ficha_id}", {
        params: { path: { ficha_id: lancamento!.ficha_id } },
      });
      return data as FichaCompleta | undefined;
    },
    enabled: !!lancamento?.ficha_id,
  });

  // Semeia o estado local com os valores ja gravados do lancamento (uma vez
  // so, na primeira vez que o lancamento chega) -- diferente da ficha em
  // branco de LancamentoFormPage, aqui o ponto de partida e o que ja foi
  // lancado, nao zero.
  useEffect(() => {
    if (!lancamento || inicializado) return;
    const iniciais: Record<string, ValorEstado> = {};
    for (const item of lancamento.itens) {
      if (!item.criterio_id) continue;
      const tipo = item.criterio_snapshot?.tipo;
      if (tipo === "MODIFICADOR") {
        iniciais[item.criterio_id] = { aplicado: !!item.criterio_snapshot?.aplicado };
      } else if (tipo === "ESCALA") {
        iniciais[item.criterio_id] = { valor: item.valor ?? undefined };
      } else {
        iniciais[item.criterio_id] = { ocorrencias: item.ocorrencias ?? 0 };
      }
    }
    setValores(iniciais);
    setTotalPreview(lancamento.total);
    setInicializado(true);
  }, [lancamento, inicializado]);

  async function simular(novosValores: Record<string, ValorEstado>) {
    if (!lancamento) return;
    const valoresPayload = Object.entries(novosValores).map(([criterio_id, valor]) => ({
      criterio_id,
      ...valor,
    }));
    const { data } = await api.POST("/api/v1/fichas/{ficha_id}/simular", {
      params: { path: { ficha_id: lancamento.ficha_id } },
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

  async function enviarCorrecao() {
    if (!lancamento || enviando) return;
    if (!justificativa.trim()) {
      setErro("Informe uma justificativa para a correção.");
      return;
    }
    setErro(null);
    setEnviando(true);

    const itens = Object.entries(valores).map(([criterio_id, valor]) => ({
      criterio_id,
      ...valor,
    }));

    const { error } = await api.POST("/api/v1/lancamentos/{lancamento_id}/corrigir", {
      params: { path: { lancamento_id: lancamentoId! } },
      body: { justificativa, revision: lancamento.revision, itens } as never,
    });

    setEnviando(false);
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    navigate(-1);
  }

  if (!lancamento || !ficha) {
    return <main className="p-8 text-slate-500">Carregando...</main>;
  }

  if (lancamento.status !== "CONFIRMADO") {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <p className="text-slate-600">
          Só é possível corrigir um lançamento já confirmado (status atual: {lancamento.status}).
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar
      </button>
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">Corrigir lançamento</h1>
      <p className="mb-6 text-sm text-slate-500">
        Alterar um lançamento já confirmado exige justificativa e fica registrado no histórico de
        auditoria.
      </p>

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
                  onIncrementar={() => alterarOcorrencias(criterio.id, 1, criterio.max_ocorrencias)}
                  onDecrementar={() =>
                    alterarOcorrencias(criterio.id, -1, criterio.max_ocorrencias)
                  }
                  onSelecionarEscala={(valor) => selecionarValorEscala(criterio.id, valor)}
                  onAlternarModificador={(aplicado) => alternarModificador(criterio.id, aplicado)}
                  onAlternarBooleano={(marcado) => alternarBooleano(criterio.id, marcado)}
                />
              ))}
            </div>
          </section>
        ))}

        <p className="text-sm text-slate-500">
          Novo total: <span className="font-semibold text-slate-800">{totalPreview ?? 0}</span>
        </p>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="justificativa">
            Justificativa da correção
          </label>
          <textarea
            id="justificativa"
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2"
            rows={3}
          />
        </div>

        {erro && <p className="text-sm text-red-600">{erro}</p>}

        <button
          type="button"
          onClick={enviarCorrecao}
          disabled={enviando}
          className="rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          {enviando ? "Salvando..." : "Salvar correção"}
        </button>
      </div>
    </main>
  );
}
