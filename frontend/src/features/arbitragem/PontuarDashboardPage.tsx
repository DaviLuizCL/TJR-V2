import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import { ModalidadeCard } from "../../components/ModalidadeCard";

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
        <EmptyState icone="🎯" titulo="Nenhuma modalidade individual cadastrada ainda neste evento.">
          A coordenação cria as modalidades em Modalidades → Nova modalidade.
        </EmptyState>
      )}

      <ul className="grid gap-4 sm:grid-cols-2">
        {individuais?.map((modalidade) => (
          <ModalidadeCard
            key={modalidade.id}
            nome={modalidade.nome}
            acaoPrincipal={
              <Link
                to={`/eventos/${eventoId}/modalidades/${modalidade.id}/pontuar`}
                className="btn-primary w-full"
              >
                Pontuar
              </Link>
            }
          />
        ))}
      </ul>
    </div>
  );
}
