import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { api } from "../../api/client";
import { PontuarCombatePage } from "./PontuarCombatePage";
import { PontuarPage } from "./PontuarPage";

export function PontuarRoutePage() {
  const { modalidadeId } = useParams<{ modalidadeId: string }>();

  const { data: modalidade } = useQuery({
    queryKey: ["modalidade", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}", {
        params: { path: { modalidade_id: modalidadeId! } },
      });
      return data as { tipo_disputa: string } | undefined;
    },
    enabled: !!modalidadeId,
  });

  if (!modalidade) {
    return (
      <main className="p-8">
        <p className="animate-pulse text-slate-500">Carregando...</p>
      </main>
    );
  }

  return modalidade.tipo_disputa === "CONFRONTO" ? <PontuarCombatePage /> : <PontuarPage />;
}
