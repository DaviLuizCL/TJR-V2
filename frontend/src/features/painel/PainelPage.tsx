import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../../api/client";
import { RankingClassificacao, type ModalidadeAba } from "../ranking/RankingClassificacao";
import { SubmissoesTab } from "./SubmissoesTab";

type Aba = "ranking" | "submissoes";

// Ranking reconectado a pedido do coordenador: uso interno (staff que ve o
// Painel), independente de `ranking_liberado` (esse campo so controla a
// exibicao PUBLICA em /eventos/:id/ranking) - RankingClassificacao ja
// buscava por modalidade sem olhar essa flag, so a aba tinha sido tirada do
// tablist numa sessao anterior por falta de tempo.
export function PainelPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const [aba, setAba] = useState<Aba>("ranking");

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

  function classesAba(valor: Aba): string {
    return `min-h-12 rounded-t px-4 py-2 text-sm font-medium ${
      aba === valor ? "border-b-2 border-slate-800 text-slate-900" : "text-slate-500"
    }`;
  }

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Painel</h1>

      <div role="tablist" className="mb-6 flex gap-2 border-b border-slate-200">
        <button
          role="tab"
          type="button"
          aria-selected={aba === "ranking"}
          onClick={() => setAba("ranking")}
          className={classesAba("ranking")}
        >
          Ranking
        </button>
        <button
          role="tab"
          type="button"
          aria-selected={aba === "submissoes"}
          onClick={() => setAba("submissoes")}
          className={classesAba("submissoes")}
        >
          Submissões
        </button>
      </div>

      {aba === "ranking" && (
        <RankingClassificacao
          modalidades={modalidades}
          mensagemVazia="Nenhuma modalidade cadastrada ainda."
        />
      )}
      {aba === "submissoes" && eventoId && (
        <SubmissoesTab eventoId={eventoId} modalidades={modalidades} />
      )}
    </main>
  );
}
