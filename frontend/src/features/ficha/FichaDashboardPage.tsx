import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";

interface ModalidadeResumo {
  id: string;
  nome: string;
  tipo_disputa: string;
}

interface FichaResumo {
  id: string;
  status: string;
}

function statusFicha(fichas: FichaResumo[] | undefined): string {
  if (!fichas || fichas.length === 0) return "Nao criada";
  if (fichas.every((f) => f.status === "PUBLICADA")) return "Publicada";
  return "Rascunho";
}

function classesStatus(texto: string): string {
  if (texto === "Publicada") return "bg-green-100 text-green-800";
  if (texto === "Rascunho") return "bg-amber-100 text-amber-800";
  return "bg-slate-100 text-slate-600";
}

function ModalidadeFichaItem({ modalidade, eventoId }: { modalidade: ModalidadeResumo; eventoId: string }) {
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
    <li className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3">
      <div>
        <p className="font-medium text-slate-800">{modalidade.nome}</p>
        <p className="text-sm text-slate-500">{modalidade.tipo_disputa}</p>
      </div>
      <div className="flex items-center gap-3">
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${classesStatus(texto)}`}>
          {texto}
        </span>
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidade.id}/fichas`}
          className="text-sm font-medium text-slate-700 underline"
        >
          Ver fichas
        </Link>
      </div>
    </li>
  );
}

export function FichaDashboardPage() {
  const { eventoId } = useParams<{ eventoId: string }>();

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
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Fichas</h1>

      {isLoading && <p className="text-slate-500">Carregando...</p>}
      {!isLoading && modalidades?.length === 0 && (
        <p className="text-slate-500">Nenhuma modalidade cadastrada ainda neste evento.</p>
      )}

      <ul className="space-y-2">
        {modalidades?.map((modalidade) => (
          <ModalidadeFichaItem key={modalidade.id} modalidade={modalidade} eventoId={eventoId!} />
        ))}
      </ul>
    </main>
  );
}
