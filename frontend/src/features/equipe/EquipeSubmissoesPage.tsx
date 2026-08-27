import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { rotuloNivel } from "../../lib/nivel";
import { ListaSubmissoes } from "../painel/ListaSubmissoes";

interface EquipeInfo {
  id: string;
  nome: string;
  nivel: number;
}

export function EquipeSubmissoesPage() {
  const { equipeId } = useParams<{ equipeId: string }>();

  const { data: equipe } = useQuery({
    queryKey: ["equipe", equipeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes/{equipe_id}", {
        params: { path: { equipe_id: equipeId! } },
      });
      return data as EquipeInfo | undefined;
    },
    enabled: !!equipeId,
  });

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link to="/equipes" className="mb-4 inline-block text-sm font-medium text-slate-600 underline">
        ← Voltar para equipes
      </Link>

      {!equipe ? (
        <p className="text-slate-500">Carregando...</p>
      ) : (
        <>
          <h1 className="mb-1 text-2xl font-semibold text-slate-800">{equipe.nome}</h1>
          <p className="mb-6 text-sm text-slate-500">{rotuloNivel(equipe.nivel)} · Submissões</p>
          <ListaSubmissoes
            equipeId={equipeId}
            mensagemVazia="Esta equipe ainda nao tem nenhuma pontuacao lancada."
          />
        </>
      )}
    </main>
  );
}
