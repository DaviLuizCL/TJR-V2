import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { api } from "../../api/client";
import type { ModalidadeAba } from "../ranking/RankingClassificacao";
import { SubmissoesTab } from "./SubmissoesTab";

// Aba "Ranking" tirada de propósito (não desligar a `RankingClassificacao`,
// só desconectar do Painel) - decisão do coordenador pro TJR 2026: tempo
// curto, ranking ainda não está pronto pra mostrar nem pro staff. Religar é
// só trazer o tablist Ranking/Submissões de volta se der tempo.
export function PainelPage() {
  const { eventoId } = useParams<{ eventoId: string }>();

  const { data: modalidades } = useQuery({
    queryKey: ["modalidades-painel", eventoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades", {
        params: { query: { evento_id: eventoId, size: 200 } },
      });
      return (data?.itens ?? []) as ModalidadeAba[];
    },
    enabled: !!eventoId,
  });

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Painel</h1>

      {eventoId && <SubmissoesTab eventoId={eventoId} modalidades={modalidades} />}
    </main>
  );
}
