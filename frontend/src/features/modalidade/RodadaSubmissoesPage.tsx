import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { ListaSubmissoes } from "../painel/ListaSubmissoes";

interface ModalidadeInfo {
  id: string;
  nome: string;
}

interface RodadaInfo {
  id: string;
  numero: number;
}

export function RodadaSubmissoesPage() {
  const { eventoId, modalidadeId, rodadaId } = useParams<{
    eventoId: string;
    modalidadeId: string;
    rodadaId: string;
  }>();

  const { data: modalidade } = useQuery({
    queryKey: ["modalidade", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}", {
        params: { path: { modalidade_id: modalidadeId! } },
      });
      return data as ModalidadeInfo | undefined;
    },
    enabled: !!modalidadeId,
  });

  const { data: rodada } = useQuery({
    queryKey: ["rodada", rodadaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/rodadas/{rodada_id}", {
        params: { path: { rodada_id: rodadaId! } },
      });
      return data as RodadaInfo | undefined;
    },
    enabled: !!rodadaId,
  });

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link
        to={`/eventos/${eventoId}/modalidades/${modalidadeId}/rodadas`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar para rodadas
      </Link>

      {!modalidade || !rodada ? (
        <p className="text-slate-500">Carregando...</p>
      ) : (
        <>
          <h1 className="mb-6 text-2xl font-semibold text-slate-800">
            Fichas enviadas · {modalidade.nome} · Rodada {rodada.numero}
          </h1>
          <ListaSubmissoes
            rodadaId={rodadaId}
            mensagemVazia="Nenhuma ficha enviada nesta rodada ainda."
          />
        </>
      )}
    </main>
  );
}
