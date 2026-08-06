import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";

interface ModalidadeInfo {
  id: string;
  nome: string;
  niveis_aplicaveis: number[];
}

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
  ativo: boolean;
}

interface InscricaoItem {
  id: string;
  equipe_id: string;
  modalidade_id: string;
}

export function InscricaoPage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId: string }>();
  const queryClient = useQueryClient();
  const [equipeSelecionada, setEquipeSelecionada] = useState("");
  const [erro, setErro] = useState<string | null>(null);

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

  const { data: equipes } = useQuery({
    queryKey: ["equipes", "ativas"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/equipes", {
        params: { query: { ativo: true, size: 200 } },
      });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  const { data: inscricoes } = useQuery({
    queryKey: ["inscricoes", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/inscricoes", {
        params: { query: { modalidade_id: modalidadeId, size: 200 } },
      });
      return (data?.itens ?? []) as InscricaoItem[];
    },
    enabled: !!modalidadeId,
  });

  async function invalidar() {
    await queryClient.invalidateQueries({ queryKey: ["inscricoes", modalidadeId] });
  }

  const equipesPorId = new Map((equipes ?? []).map((e) => [e.id, e]));
  const inscritas = (inscricoes ?? [])
    .map((inscricao) => ({ inscricao, equipe: equipesPorId.get(inscricao.equipe_id) }))
    .filter((item) => item.equipe);

  const idsInscritos = new Set((inscricoes ?? []).map((i) => i.equipe_id));
  const elegiveis = (equipes ?? []).filter(
    (equipe) =>
      !idsInscritos.has(equipe.id) &&
      (modalidade?.niveis_aplicaveis ?? []).includes(equipe.nivel),
  );

  async function inscrever(evento: FormEvent) {
    evento.preventDefault();
    if (!equipeSelecionada || !modalidadeId) return;
    setErro(null);

    const { error } = await api.POST("/api/v1/inscricoes", {
      body: { equipe_id: equipeSelecionada, modalidade_id: modalidadeId },
    });

    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }

    setEquipeSelecionada("");
    await invalidar();
  }

  async function remover(inscricaoId: string) {
    await api.DELETE("/api/v1/inscricoes/{inscricao_id}", {
      params: { path: { inscricao_id: inscricaoId } },
    });
    await invalidar();
  }

  if (!modalidade || !equipes || !inscricoes) {
    return <main className="p-8 text-slate-500">Carregando...</main>;
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link
        to={`/eventos/${eventoId}/modalidades`}
        className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
      >
        ← Voltar para modalidades
      </Link>
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">
        Inscricoes de {modalidade?.nome ?? "..."}
      </h1>

      <ul className="mb-8 space-y-2">
        {inscritas.map(({ inscricao, equipe }) => (
          <li
            key={inscricao.id}
            className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3"
          >
            <div>
              <span className="font-medium text-slate-800">{equipe!.nome}</span>
              <span className="ml-2 text-sm text-slate-500">Nivel {equipe!.nivel}</span>
            </div>
            <button
              type="button"
              onClick={() => remover(inscricao.id)}
              className="text-sm font-medium text-red-700 underline"
            >
              Remover
            </button>
          </li>
        ))}
        {inscritas.length === 0 && (
          <p className="text-slate-500">Nenhuma equipe inscrita ainda.</p>
        )}
      </ul>

      <form onSubmit={inscrever} className="flex items-end gap-2">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="equipe">
            Equipe
          </label>
          <select
            id="equipe"
            value={equipeSelecionada}
            onChange={(e) => setEquipeSelecionada(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2"
          >
            <option value="">Selecione uma equipe</option>
            {elegiveis.map((equipe) => (
              <option key={equipe.id} value={equipe.id}>
                {equipe.nome} (Nivel {equipe.nivel})
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={!equipeSelecionada}
          className="rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          Inscrever
        </button>
      </form>
      {erro && <p className="mt-2 text-sm text-red-600">{erro}</p>}
    </main>
  );
}
