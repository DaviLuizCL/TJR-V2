import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import { ModalidadeCard } from "../../components/ModalidadeCard";
import { useAuthStore } from "../../lib/auth-store";

interface ModalidadeResumo {
  id: string;
  nome: string;
  tipo_disputa: string;
  formato_chaveamento: string | null;
}

const LABELS_FORMATO: Record<string, string> = {
  MATA_MATA: "Mata-Mata",
  TODOS_CONTRA_TODOS: "Todos contra Todos",
};

function ModalidadeCombateItem({
  modalidade,
  eventoId,
}: {
  modalidade: ModalidadeResumo;
  eventoId: string;
}) {
  const ehArbitro = useAuthStore((state) => state.usuario?.papel) === "ARBITRO";
  return (
    <ModalidadeCard
      nome={modalidade.nome}
      selo={
        <span
          className="chip border-plasma/40 bg-plasma-soft text-plasma"
          title={
            modalidade.formato_chaveamento
              ? undefined
              : "Os confrontos são criados na mão pela coordenação, que escolhe em cada um se é fase de grupos ou eliminatória."
          }
        >
          {modalidade.formato_chaveamento
            ? (LABELS_FORMATO[modalidade.formato_chaveamento] ??
              "Sem formato definido")
            : "Montado na mão"}
        </span>
      }
      acaoPrincipal={
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidade.id}/pontuar`}
          className="btn-primary flex-1"
        >
          Pontuar
        </Link>
      }
      acoesSecundarias={
        !ehArbitro && (
          <Link
            to={`/eventos/${eventoId}/modalidades/${modalidade.id}/rodadas`}
            className="btn-secondary flex-1"
          >
            Ver confrontos
          </Link>
        )
      }
    />
  );
}

export function CombateDashboardPage() {
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

  const combates = modalidades?.filter((m) => m.tipo_disputa === "CONFRONTO");

  return (
    <div>
      {isLoading && <p className="text-slate-500">Carregando...</p>}
      {!isLoading && combates?.length === 0 && (
        <EmptyState
          icone="⚔️"
          titulo="Nenhuma modalidade de combate cadastrada ainda neste evento."
        >
          A coordenação cria as modalidades em Modalidades → Nova modalidade.
        </EmptyState>
      )}

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {combates?.map((modalidade) => (
          <ModalidadeCombateItem
            key={modalidade.id}
            modalidade={modalidade}
            eventoId={eventoId!}
          />
        ))}
      </ul>
    </div>
  );
}
