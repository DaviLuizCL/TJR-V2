import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";

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
  return (
    <li className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3">
      <p className="font-medium text-slate-800">{modalidade.nome}</p>
      <div className="flex items-center gap-3">
        <span
          className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
          title={
            modalidade.formato_chaveamento
              ? undefined
              : "Decidido por nível ao gerar o chaveamento: até 5 equipes vira todos-contra-todos, 6 ou mais vira mata-mata."
          }
        >
          {modalidade.formato_chaveamento
            ? (LABELS_FORMATO[modalidade.formato_chaveamento] ?? "Sem formato definido")
            : "Automático por nível"}
        </span>
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidade.id}/pontuar`}
          className="text-sm font-medium text-slate-700 underline"
        >
          Pontuar
        </Link>
        <Link
          to={`/eventos/${eventoId}/modalidades/${modalidade.id}/rodadas`}
          className="text-sm font-medium text-slate-700 underline"
        >
          Ver rodadas
        </Link>
      </div>
    </li>
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
        <p className="text-slate-500">Nenhuma modalidade de combate cadastrada ainda neste evento.</p>
      )}

      <ul className="space-y-2">
        {combates?.map((modalidade) => (
          <ModalidadeCombateItem key={modalidade.id} modalidade={modalidade} eventoId={eventoId!} />
        ))}
      </ul>
    </div>
  );
}
