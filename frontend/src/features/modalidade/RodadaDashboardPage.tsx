import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";

interface ModalidadeResumo {
  id: string;
  nome: string;
  qtd_rodadas: number;
  tipo_disputa: string;
}

function ModalidadeRodadaItem({
  modalidade,
  eventoId,
}: {
  modalidade: ModalidadeResumo;
  eventoId: string;
}) {
  const { data: rodadas } = useQuery({
    queryKey: ["rodadas-total", modalidade.id],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas", {
        params: { query: { modalidade_id: modalidade.id, size: 200 } },
      });
      return data?.total ?? 0;
    },
  });

  return (
    <li className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3">
      <p className="font-medium text-slate-800">{modalidade.nome}</p>
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
          {rodadas ?? 0}/{modalidade.qtd_rodadas} rodadas criadas
        </span>
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

export function RodadaDashboardPage() {
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
          <ModalidadeRodadaItem key={modalidade.id} modalidade={modalidade} eventoId={eventoId!} />
        ))}
      </ul>
    </div>
  );
}
