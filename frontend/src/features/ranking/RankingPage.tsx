import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { api } from "../../api/client";
import { RankingClassificacao, type ModalidadeAba } from "./RankingClassificacao";

export function RankingPage() {
  const { eventoId } = useParams<{ eventoId: string }>();

  const { data: modalidades } = useQuery({
    queryKey: ["ranking-modalidades", eventoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/ranking/modalidades", {
        params: { query: { evento_id: eventoId! } },
      });
      return (data ?? []) as ModalidadeAba[];
    },
    enabled: !!eventoId,
  });

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Classificacao</h1>
      <RankingClassificacao modalidades={modalidades} mensagemVazia="Nenhum ranking liberado ainda." />
    </main>
  );
}
