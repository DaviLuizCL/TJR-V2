import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";

interface ModalidadeResumo {
  id: string;
  nome: string;
  tipo_disputa: string;
}

export function PontuarDashboardPage() {
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

  const individuais = modalidades?.filter((m) => m.tipo_disputa === "INDIVIDUAL");

  return (
    <div>
      {isLoading && <p className="text-slate-500">Carregando...</p>}
      {!isLoading && individuais?.length === 0 && (
        <p className="text-slate-500">Nenhuma modalidade individual cadastrada ainda neste evento.</p>
      )}

      <ul className="space-y-2">
        {individuais?.map((modalidade) => (
          <li
            key={modalidade.id}
            className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3"
          >
            <p className="font-medium text-slate-800">{modalidade.nome}</p>
            <Link
              to={`/eventos/${eventoId}/modalidades/${modalidade.id}/pontuar`}
              className="text-sm font-medium text-slate-700 underline"
            >
              Pontuar
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
