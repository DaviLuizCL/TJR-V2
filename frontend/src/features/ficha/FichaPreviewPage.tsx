import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";

export interface CriterioItem {
  id: string;
  nome: string;
  categoria: string;
  tipo: string;
  pontos: number | null;
  valores_permitidos: number[] | null;
  max_ocorrencias: number | null;
  modificador_tipo: string | null;
  modificador_valor: number | null;
}

interface GrupoItem {
  id: string;
  nome: string;
  criterios: CriterioItem[];
}

interface FichaCompleta {
  id: string;
  modalidade_id: string;
  nivel: number | null;
  grupos: GrupoItem[];
}

interface FichaResumo {
  id: string;
  nivel: number | null;
  versao: number;
  status: string;
}

export interface ValorEstado {
  ocorrencias?: number;
  valor?: number;
  aplicado?: boolean;
}

interface SimulacaoResultado {
  total: number;
}

function estiloContainer(ativo: boolean, categoria: string): string {
  if (ativo && categoria === "PENALIDADE") {
    return "flex min-h-12 items-center justify-between rounded border border-red-300 bg-red-50 px-3 py-2";
  }
  return "flex min-h-12 items-center justify-between rounded border border-slate-200 bg-white px-3 py-2";
}

export function CriterioPreview({
  criterio,
  valor,
  onIncrementar,
  onDecrementar,
  onSelecionarEscala,
  onAlternarModificador,
  onAlternarBooleano,
}: {
  criterio: CriterioItem;
  valor: ValorEstado | undefined;
  onIncrementar: () => void;
  onDecrementar: () => void;
  onSelecionarEscala: (valor: number) => void;
  onAlternarModificador: (aplicado: boolean) => void;
  onAlternarBooleano: (marcado: boolean) => void;
}) {
  if (criterio.tipo === "MODIFICADOR") {
    const aplicado = valor?.aplicado ?? false;
    return (
      <label
        data-testid={`criterio-${criterio.id}`}
        className={estiloContainer(aplicado, criterio.categoria)}
      >
        <span className="text-sm text-slate-800">{criterio.nome}</span>
        <input
          type="checkbox"
          className="h-6 w-6"
          checked={aplicado}
          onChange={(evento) => onAlternarModificador(evento.target.checked)}
        />
      </label>
    );
  }

  if (criterio.tipo === "BOOLEANO") {
    // Booleano e fez-ou-nao-fez: nao faz sentido ter mais de uma ocorrencia,
    // entao usa o mesmo tipo de controle do modificador (toggle), nao +/-.
    const marcado = (valor?.ocorrencias ?? 0) > 0;
    return (
      <label
        data-testid={`criterio-${criterio.id}`}
        className={estiloContainer(marcado, criterio.categoria)}
      >
        <div>
          <p className="text-sm text-slate-800">{criterio.nome}</p>
          {criterio.pontos !== null && (
            <p className="text-xs text-slate-500">{criterio.pontos} pts</p>
          )}
        </div>
        <input
          type="checkbox"
          className="h-6 w-6"
          checked={marcado}
          onChange={(evento) => onAlternarBooleano(evento.target.checked)}
        />
      </label>
    );
  }

  if (criterio.tipo === "ESCALA") {
    return (
      <div
        data-testid={`criterio-${criterio.id}`}
        className="rounded border border-slate-200 bg-white p-3"
      >
        <p className="mb-2 text-sm text-slate-800">{criterio.nome}</p>
        <div className="flex flex-wrap gap-2">
          {(criterio.valores_permitidos ?? []).map((opcao) => {
            const selecionado = valor?.valor === opcao;
            const corSelecionado =
              criterio.categoria === "PENALIDADE"
                ? "border-red-600 bg-red-600 text-white"
                : "border-slate-800 bg-slate-800 text-white";
            return (
              <button
                key={opcao}
                type="button"
                onClick={() => onSelecionarEscala(opcao)}
                className={`flex min-h-12 min-w-12 items-center justify-center rounded border px-3 font-semibold ${
                  selecionado ? corSelecionado : "border-slate-300 text-slate-700"
                }`}
              >
                {opcao}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  const ocorrencias = valor?.ocorrencias ?? 0;

  return (
    <div
      data-testid={`criterio-${criterio.id}`}
      className={estiloContainer(ocorrencias > 0, criterio.categoria)}
    >
      <div>
        <p className="text-sm text-slate-800">{criterio.nome}</p>
        {criterio.pontos !== null && (
          <p className="text-xs text-slate-500">{criterio.pontos} pts</p>
        )}
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onDecrementar}
          aria-label={`Diminuir ${criterio.nome}`}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-2xl font-bold text-slate-700"
        >
          −
        </button>
        <span className="w-6 text-center text-lg font-semibold text-slate-800">
          {ocorrencias}
        </span>
        <button
          type="button"
          onClick={onIncrementar}
          aria-label={`Aumentar ${criterio.nome}`}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-2xl font-bold text-white"
        >
          +
        </button>
      </div>
    </div>
  );
}

export function FichaPreviewPage() {
  const { eventoId, modalidadeId, fichaId } = useParams<{
    eventoId: string;
    modalidadeId: string;
    fichaId: string;
  }>();
  const navigate = useNavigate();
  const [valores, setValores] = useState<Record<string, ValorEstado>>({});
  const [resultado, setResultado] = useState<SimulacaoResultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const { data: ficha } = useQuery({
    queryKey: ["ficha-preview", fichaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas/{ficha_id}", {
        params: { path: { ficha_id: fichaId! } },
      });
      return data as FichaCompleta | undefined;
    },
    enabled: !!fichaId,
  });

  const { data: fichasDaModalidade } = useQuery({
    queryKey: ["fichas-da-modalidade", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas", {
        params: { query: { modalidade_id: modalidadeId, size: 100 } },
      });
      return data?.itens as FichaResumo[] | undefined;
    },
    enabled: !!modalidadeId,
  });

  async function simular(novosValores: Record<string, ValorEstado>) {
    setErro(null);
    const valoresPayload = Object.entries(novosValores).map(([criterio_id, valor]) => ({
      criterio_id,
      ...valor,
    }));

    const { data, error } = await api.POST("/api/v1/fichas/{ficha_id}/simular", {
      params: { path: { ficha_id: fichaId! } },
      body: { valores: valoresPayload } as never,
    });

    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }

    setResultado(data as SimulacaoResultado);
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

  function trocarFicha(novoFichaId: string) {
    navigate(`/eventos/${eventoId}/modalidades/${modalidadeId}/fichas/${novoFichaId}/preview`);
  }

  if (!ficha) {
    return <main className="p-6 text-slate-500">Carregando...</main>;
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col bg-slate-50 pb-28">
      <header className="sticky top-0 z-10 bg-white px-4 py-3 shadow-sm">
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidadeId}/fichas/${fichaId}/editar`}
          className="mb-1 inline-block text-sm font-medium text-slate-600 underline"
        >
          ← Voltar para o editor
        </Link>
        <h1 className="text-lg font-semibold text-slate-800">Preview da ficha</h1>
        <p className="mb-2 text-xs text-slate-500">Simulacao — nao lanca pontuacao real</p>

        {fichasDaModalidade && fichasDaModalidade.length > 1 && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="seletor-ficha">
              Selecionar ficha
            </label>
            <select
              id="seletor-ficha"
              value={fichaId}
              onChange={(evento) => trocarFicha(evento.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              {fichasDaModalidade
                .filter((f) => f.status !== "SUBSTITUIDA")
                .map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.nivel === null ? "Ficha unica" : `Nivel ${f.nivel}`} · {f.status}
                  </option>
                ))}
            </select>
          </div>
        )}
      </header>

      <div className="flex-1 space-y-4 p-4">
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
      </div>

      {erro && <p className="mx-4 mb-2 rounded bg-red-100 px-3 py-2 text-sm text-red-800">{erro}</p>}

      <footer className="sticky bottom-0 z-10 border-t border-slate-200 bg-white px-4 py-4">
        <p className="text-sm text-slate-500">Total parcial</p>
        <p data-testid="total-parcial" className="text-3xl font-bold text-slate-900">
          {resultado?.total ?? 0}
        </p>
      </footer>
    </div>
  );
}
