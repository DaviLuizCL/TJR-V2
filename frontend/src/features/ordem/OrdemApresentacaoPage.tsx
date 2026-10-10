import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { rotuloNivel } from "../../lib/nivel";

interface ModalidadeInfo {
  id: string;
  nome: string;
}

interface InscricaoItem {
  equipe_id: string;
  ordem_apresentacao?: number | null;
}

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
  ativo: boolean;
}

interface EquipeNaOrdem {
  id: string;
  nome: string;
  ordem: number | null;
}

function ordenar(equipes: EquipeNaOrdem[]): EquipeNaOrdem[] {
  return [...equipes].sort((a, b) => {
    const ordemA = a.ordem ?? Number.POSITIVE_INFINITY;
    const ordemB = b.ordem ?? Number.POSITIVE_INFINITY;
    if (ordemA !== ordemB) return ordemA - ordemB;
    return a.nome.localeCompare(b.nome);
  });
}

function SecaoNivel({
  modalidadeId,
  nivel,
  equipes,
  podeEditar,
  onAlterado,
}: {
  modalidadeId: string;
  nivel: number;
  equipes: EquipeNaOrdem[];
  podeEditar: boolean;
  onAlterado: () => Promise<void>;
}) {
  const [confirmandoSorteio, setConfirmandoSorteio] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const jaSorteada = equipes.some((e) => e.ordem !== null);
  const rotulo = rotuloNivel(nivel);
  const idTitulo = `titulo-nivel-${nivel}`;

  async function sortear() {
    setConfirmandoSorteio(false);
    setSalvando(true);
    setErro(null);
    const { error } = await api.POST(
      "/api/v1/modalidades/{modalidade_id}/ordem-apresentacao/sortear",
      { params: { path: { modalidade_id: modalidadeId } }, body: { nivel } },
    );
    if (error) setErro(extrairErro(error).mensagem);
    await onAlterado();
    setSalvando(false);
  }

  async function mover(indice: number, deslocamento: -1 | 1) {
    const novaOrdem = equipes.map((e) => e.id);
    const destino = indice + deslocamento;
    [novaOrdem[indice], novaOrdem[destino]] = [novaOrdem[destino], novaOrdem[indice]];
    setSalvando(true);
    setErro(null);
    const { error } = await api.PUT("/api/v1/modalidades/{modalidade_id}/ordem-apresentacao", {
      params: { path: { modalidade_id: modalidadeId } },
      body: { nivel, equipe_ids: novaOrdem },
    });
    if (error) setErro(extrairErro(error).mensagem);
    await onAlterado();
    setSalvando(false);
  }

  return (
    <section
      aria-labelledby={idTitulo}
      className="mb-6 rounded-lg border border-slate-200 bg-white p-4"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 id={idTitulo} className="text-lg font-semibold text-slate-800">
          {rotulo}
        </h2>
        {podeEditar && !jaSorteada && (
          <button
            type="button"
            onClick={sortear}
            disabled={salvando}
            className="min-h-12 rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            🎲 Sortear ordem
          </button>
        )}
        {podeEditar && jaSorteada && !confirmandoSorteio && (
          <button
            type="button"
            onClick={() => setConfirmandoSorteio(true)}
            disabled={salvando}
            className="min-h-12 rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
          >
            🎲 Sortear de novo
          </button>
        )}
      </div>

      {confirmandoSorteio && (
        <div className="mb-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="mb-2">
            A ordem atual deste nível vai ser substituída por um sorteio novo. Tem certeza?
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={sortear}
              className="min-h-12 rounded bg-amber-700 px-4 py-2 font-medium text-white"
            >
              Sim, sortear de novo
            </button>
            <button
              type="button"
              onClick={() => setConfirmandoSorteio(false)}
              className="min-h-12 rounded border border-amber-400 px-4 py-2 font-medium"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {!jaSorteada && (
        <p className="mb-3 text-sm text-amber-800">
          A ordem ainda não foi sorteada. Enquanto isso, a tela de pontuar mostra as equipes em
          ordem alfabética.
        </p>
      )}
      {erro && <p className="mb-3 text-sm text-red-600">{erro}</p>}

      <ol className="space-y-2">
        {equipes.map((equipe, indice) => (
          <li
            key={equipe.id}
            className="flex items-center gap-3 rounded border border-slate-200 px-3 py-2"
          >
            <span className="w-8 text-right text-lg font-semibold text-slate-500">
              {jaSorteada ? `${indice + 1}º` : "–"}
            </span>
            <span data-testid="nome-equipe" className="flex-1 font-medium text-slate-800">
              {equipe.nome}
            </span>
            {podeEditar && jaSorteada && (
              <>
                <button
                  type="button"
                  aria-label={`Subir ${equipe.nome}`}
                  onClick={() => mover(indice, -1)}
                  disabled={salvando || indice === 0}
                  className="h-12 w-12 rounded border border-slate-300 text-lg disabled:opacity-30"
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Descer ${equipe.nome}`}
                  onClick={() => mover(indice, 1)}
                  disabled={salvando || indice === equipes.length - 1}
                  className="h-12 w-12 rounded border border-slate-300 text-lg disabled:opacity-30"
                >
                  ↓
                </button>
              </>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function OrdemApresentacaoPage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId: string }>();
  const queryClient = useQueryClient();
  const podeEditar = useAuthStore((state) => state.usuario?.papel) === "COORDENADOR";
  const [gerandoPdf, setGerandoPdf] = useState(false);
  const [erroPdf, setErroPdf] = useState<string | null>(null);

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

  const { data: inscricoes } = useQuery({
    queryKey: ["inscricoes", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/inscricoes", {
        params: { query: { modalidade_id: modalidadeId, size: 1000 } },
      });
      return (data?.itens ?? []) as InscricaoItem[];
    },
    enabled: !!modalidadeId,
  });

  const { data: equipes } = useQuery({
    queryKey: ["equipes", "para-ordem"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  async function recarregar() {
    await queryClient.invalidateQueries({ queryKey: ["inscricoes", modalidadeId] });
  }

  async function baixarPdf() {
    setGerandoPdf(true);
    setErroPdf(null);
    const { data, error } = await api.GET(
      "/api/v1/modalidades/{modalidade_id}/sequencia-competicao.pdf",
      { params: { path: { modalidade_id: modalidadeId! } }, parseAs: "blob" },
    );
    setGerandoPdf(false);
    if (error || !data) {
      setErroPdf(extrairErro(error).mensagem);
      return;
    }
    const url = URL.createObjectURL(data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sequencia-${modalidade?.nome ?? "competicao"}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (!modalidade || !inscricoes || !equipes) {
    return (
      <main className="p-8">
        <p className="animate-pulse text-slate-500">Carregando...</p>
      </main>
    );
  }

  const equipePorId = new Map(equipes.map((e) => [e.id, e]));
  const porNivel = new Map<number, EquipeNaOrdem[]>();
  for (const inscricao of inscricoes) {
    const equipe = equipePorId.get(inscricao.equipe_id);
    if (!equipe || !equipe.ativo) continue;
    const lista = porNivel.get(equipe.nivel) ?? [];
    lista.push({ id: equipe.id, nome: equipe.nome, ordem: inscricao.ordem_apresentacao ?? null });
    porNivel.set(equipe.nivel, lista);
  }
  const niveis = [...porNivel.keys()].sort((a, b) => a - b);

  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-8">
      <Link
        to={`/eventos/${eventoId}/competicoes?aba=individual&sub=ordem`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar
      </Link>
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">
        Sequência de competição · {modalidade.nome}
      </h1>
      <p className="mb-4 text-sm text-slate-500">
        A mesma ordem vale para todas as rodadas. A arena é decidida na hora: a próxima equipe da
        lista vai para a arena que estiver livre.
      </p>
      <div className="mb-6">
        <button
          type="button"
          onClick={baixarPdf}
          disabled={gerandoPdf}
          className="min-h-12 rounded border border-slate-300 bg-white px-4 font-medium text-slate-800 disabled:opacity-50"
        >
          {gerandoPdf ? "Gerando PDF..." : "📺 Gerar PDF pro telão"}
        </button>
        <p className="mt-1 text-xs text-slate-500">
          Uma página por nível, com letra grande pra projetar.
        </p>
        {erroPdf && <p className="mt-1 text-sm font-medium text-red-600">{erroPdf}</p>}
      </div>

      {niveis.length === 0 && (
        <p className="text-slate-500">Nenhuma equipe inscrita nesta modalidade ainda.</p>
      )}
      {niveis.map((nivel) => (
        <SecaoNivel
          key={nivel}
          modalidadeId={modalidadeId!}
          nivel={nivel}
          equipes={ordenar(porNivel.get(nivel)!)}
          podeEditar={podeEditar}
          onAlterado={recarregar}
        />
      ))}
    </main>
  );
}
