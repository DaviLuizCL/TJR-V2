import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { useAuthStore } from "../../lib/auth-store";
import { useEventoStore } from "../../lib/evento-store";

interface ModalidadeResumo {
  id: string;
  nome: string;
  tipo_disputa: string;
  status: string;
  formato_chaveamento?: string | null;
}

interface FichaResumo {
  id: string;
  status: string;
}

function statusFicha(fichas: FichaResumo[] | undefined): string {
  if (!fichas || fichas.length === 0) return "Ficha: nao criada";
  if (fichas.every((f) => f.status === "PUBLICADA")) return "Ficha: publicada";
  return "Ficha: rascunho";
}

function classesStatusFicha(texto: string): string {
  if (texto.includes("publicada")) return "bg-green-100 text-green-800";
  if (texto.includes("rascunho")) return "bg-amber-100 text-amber-800";
  return "bg-slate-100 text-slate-600";
}

function ModalidadeItem({
  modalidade,
  eventoId,
}: {
  modalidade: ModalidadeResumo;
  eventoId: string;
}) {
  const { data: fichas } = useQuery({
    queryKey: ["fichas", modalidade.id],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas", {
        params: { query: { modalidade_id: modalidade.id, size: 50 } },
      });
      return data?.itens as FichaResumo[] | undefined;
    },
  });

  const texto = statusFicha(fichas);

  return (
    <li className="rounded border border-slate-200 bg-white px-4 py-3 hover:border-slate-400">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidade.id}/editar`}
          className="min-w-0 flex-1"
        >
          <p className="font-medium text-slate-800">{modalidade.nome}</p>
          <p className="text-sm text-slate-500">{modalidade.tipo_disputa}</p>
        </Link>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            {modalidade.status}
          </span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${classesStatusFicha(texto)}`}
          >
            {texto}
          </span>
          <Link
            to={`/eventos/${eventoId}/modalidades/${modalidade.id}/fichas`}
            className="inline-flex min-h-10 items-center text-sm font-medium text-slate-700 underline"
          >
            Fichas
          </Link>
          <Link
            to={`/eventos/${eventoId}/modalidades/${modalidade.id}/inscricoes`}
            className="inline-flex min-h-10 items-center text-sm font-medium text-slate-700 underline"
          >
            Inscrições
          </Link>
          <Link
            to={`/eventos/${eventoId}/modalidades/${modalidade.id}/rodadas`}
            className="inline-flex min-h-10 items-center text-sm font-medium text-slate-700 underline"
          >
            Rodadas
          </Link>
        </div>
      </div>
    </li>
  );
}

export function ModalidadeListPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const definirEventoAtual = useEventoStore((state) => state.definirEventoAtual);
  const [erroRelatorio, setErroRelatorio] = useState<string | null>(null);
  const ehCoordenador = useAuthStore((state) => state.usuario?.papel) === "COORDENADOR";

  async function baixarRelatorioGeral() {
    setErroRelatorio(null);
    const { data, error } = await api.GET(
      "/api/v1/ranking/eventos/{evento_id}/relatorio-auditoria.pdf",
      {
        params: { path: { evento_id: eventoId! } },
        parseAs: "blob",
      },
    );

    if (error || !data) {
      setErroRelatorio(extrairErro(error).mensagem);
      return;
    }

    const url = URL.createObjectURL(data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "relatorio-geral.pdf";
    link.click();
    URL.revokeObjectURL(url);
  }

  useEffect(() => {
    if (eventoId) definirEventoAtual(eventoId);
  }, [eventoId, definirEventoAtual]);

  const { data: modalidades, isLoading } = useQuery({
    queryKey: ["modalidades", eventoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades", {
        params: { query: { evento_id: eventoId, size: 100 } },
      });
      return data?.itens as ModalidadeResumo[] | undefined;
    },
    enabled: !!eventoId,
  });

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">Modalidades</h1>
        <div className="flex flex-wrap items-center gap-3">
          {ehCoordenador && (
            <Link
              to="/equipes"
              className="text-sm font-medium text-slate-700 underline"
            >
              Gerenciar equipes
            </Link>
          )}
          {ehCoordenador && !!modalidades?.length && (
            <button
              type="button"
              onClick={baixarRelatorioGeral}
              className="rounded border border-slate-300 px-4 py-2 font-medium text-slate-700"
            >
              Baixar relatório geral (PDF)
            </button>
          )}
          {ehCoordenador && (
            <Link
              to={`/eventos/${eventoId}/modalidades/novo`}
              className="btn-primary"
            >
              Nova modalidade
            </Link>
          )}
        </div>
      </div>

      {erroRelatorio && <Aviso tipo="erro" className="mb-4">{erroRelatorio}</Aviso>}

      {isLoading && <p className="text-slate-500">Carregando...</p>}
      {!isLoading && modalidades?.length === 0 && (
        <p className="text-slate-500">Nenhuma modalidade cadastrada ainda.</p>
      )}

      <ul className="space-y-2">
        {modalidades?.map((modalidade) => (
          <ModalidadeItem key={modalidade.id} modalidade={modalidade} eventoId={eventoId!} />
        ))}
      </ul>

    </main>
  );
}
