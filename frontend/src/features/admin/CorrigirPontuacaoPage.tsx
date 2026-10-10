import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { rotuloNivel } from "../../lib/nivel";
import { VoltarAdmin } from "./VoltarAdmin";

interface ModalidadeResumo {
  id: string;
  nome: string;
}

interface LancamentoResumo {
  id: string;
  nivel: number | null;
  equipe_nome: string;
  rodada_numero: number;
  tentativa: number;
  responsavel_nome: string;
  status: string;
  total: number;
}

const ROTULO_STATUS: Record<string, string> = {
  PENDENTE: "Registrada, não confirmada",
  CONFIRMADO: "Confirmada",
  ANULADO: "Anulada",
};

function LinhaLancamento({
  lancamento,
  onAnulado,
}: {
  lancamento: LancamentoResumo;
  onAnulado: () => Promise<void>;
}) {
  const [anulando, setAnulando] = useState(false);
  const [justificativa, setJustificativa] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const anulado = lancamento.status === "ANULADO";

  async function anular() {
    setEnviando(true);
    setErro(null);
    const { error } = await api.POST("/api/v1/lancamentos/{lancamento_id}/anular", {
      params: { path: { lancamento_id: lancamento.id } },
      body: { justificativa: justificativa.trim() },
    });
    setEnviando(false);
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    setAnulando(false);
    await onAnulado();
  }

  return (
    <li
      className={`rounded-lg border p-4 ${anulado ? "border-slate-200 bg-slate-50 opacity-60" : "border-slate-200 bg-white"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold text-slate-800">{lancamento.equipe_nome}</p>
          <p className="text-sm text-slate-500">
            {lancamento.nivel ? `${rotuloNivel(lancamento.nivel)} · ` : ""}
            Rodada {lancamento.rodada_numero} · Tentativa {lancamento.tentativa} · por{" "}
            {lancamento.responsavel_nome}
          </p>
          <p className="mt-1 text-sm">
            <span className="font-semibold text-slate-800">{lancamento.total} pontos</span>
            <span className="ml-2 text-slate-500">
              ({ROTULO_STATUS[lancamento.status] ?? lancamento.status})
            </span>
          </p>
        </div>
        {!anulado && !anulando && (
          <div className="flex gap-2">
            {lancamento.status === "CONFIRMADO" && (
              <Link
                to={`/lancamentos/${lancamento.id}/corrigir`}
                className="flex min-h-12 items-center rounded border border-slate-300 px-4 text-sm font-medium text-slate-700"
              >
                ✏️ Corrigir nota
              </Link>
            )}
            <button
              type="button"
              onClick={() => setAnulando(true)}
              className="min-h-12 rounded border border-red-300 px-4 text-sm font-medium text-red-700"
            >
              🗑 Anular
            </button>
          </div>
        )}
      </div>

      {anulando && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900">
          <p className="mb-2">
            A nota de <strong>{lancamento.equipe_nome}</strong> deixa de contar e a equipe volta a
            aparecer como pendente pra ser pontuada de novo nesta rodada. O registro não é apagado:
            fica no histórico como anulado.
          </p>
          <label className="mb-1 block font-medium" htmlFor={`justificativa-${lancamento.id}`}>
            Por que está anulando?
          </label>
          <textarea
            id={`justificativa-${lancamento.id}`}
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            rows={2}
            className="mb-2 w-full rounded border border-red-300 bg-white px-3 py-2 text-slate-800"
          />
          {erro && <p className="mb-2 font-medium text-red-700">{erro}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={anular}
              disabled={!justificativa.trim() || enviando}
              className="min-h-12 rounded bg-red-700 px-4 font-medium text-white disabled:opacity-50"
            >
              {enviando ? "Anulando..." : "Sim, anular"}
            </button>
            <button
              type="button"
              onClick={() => {
                setAnulando(false);
                setErro(null);
              }}
              className="min-h-12 rounded border border-red-300 px-4 font-medium"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

export function CorrigirPontuacaoPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const queryClient = useQueryClient();
  const [modalidadeId, setModalidadeId] = useState("");
  const [busca, setBusca] = useState("");

  const { data: modalidades } = useQuery({
    queryKey: ["modalidades", eventoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades", {
        params: { query: { evento_id: eventoId, size: 100 } },
      });
      return (data?.itens ?? []) as ModalidadeResumo[];
    },
    enabled: !!eventoId,
  });

  const { data: lancamentos, isLoading } = useQuery({
    queryKey: ["admin-lancamentos", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/lancamentos/auditoria", {
        params: { query: { modalidade_id: modalidadeId, size: 200 } },
      });
      return (data?.itens ?? []) as LancamentoResumo[];
    },
    enabled: !!modalidadeId,
  });

  const termo = busca.trim().toLowerCase();
  const filtrados = (lancamentos ?? []).filter(
    (l) => termo === "" || l.equipe_nome.toLowerCase().includes(termo),
  );

  async function recarregar() {
    await queryClient.invalidateQueries({ queryKey: ["admin-lancamentos", modalidadeId] });
  }

  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-8">
      <VoltarAdmin />
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">Corrigir pontuação</h1>
      <p className="mb-6 text-sm text-slate-500">
        Escolha a modalidade e ache a equipe. <strong>Corrigir</strong> muda os pontos de uma
        nota já confirmada. <strong>Anular</strong> descarta a nota (por exemplo, se o juiz
        pontuou a equipe errada) e libera a equipe pra ser pontuada de novo.
      </p>

      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="modalidade">
            Modalidade
          </label>
          <select
            id="modalidade"
            value={modalidadeId}
            onChange={(e) => setModalidadeId(e.target.value)}
            className="min-h-12 w-full rounded border border-slate-300 px-3"
          >
            <option value="">Escolha...</option>
            {(modalidades ?? []).map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="busca">
            Buscar equipe
          </label>
          <input
            id="busca"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Digite parte do nome"
            className="min-h-12 w-full rounded border border-slate-300 px-3"
          />
        </div>
      </div>

      {modalidadeId && isLoading && <p className="text-slate-500">Carregando...</p>}
      {modalidadeId && !isLoading && filtrados.length === 0 && (
        <p className="text-slate-500">Nenhuma nota encontrada.</p>
      )}

      <ul className="space-y-3">
        {filtrados.map((lancamento) => (
          <LinhaLancamento key={lancamento.id} lancamento={lancamento} onAnulado={recarregar} />
        ))}
      </ul>
    </main>
  );
}
