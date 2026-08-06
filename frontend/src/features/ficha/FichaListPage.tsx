import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";

interface FichaResumo {
  id: string;
  nivel: number | null;
  versao: number;
  status: string;
}

interface ModalidadeInfo {
  id: string;
  nome: string;
  niveis_aplicaveis: number[];
  ficha_unica_entre_niveis: boolean;
}

function SlotFicha({
  nivel,
  ficha,
  eventoId,
  modalidadeId,
  onCriar,
  onExcluida,
}: {
  nivel: number | null;
  ficha: FichaResumo | undefined;
  eventoId: string;
  modalidadeId: string;
  onCriar: (nivel: number | null) => void;
  onExcluida: () => void;
}) {
  const [erro, setErro] = useState<{ codigo: string; mensagem: string } | null>(null);

  async function excluir() {
    if (!ficha) return;
    if (!window.confirm("Excluir esta ficha? Essa acao nao pode ser desfeita.")) return;

    setErro(null);
    const { error } = await api.DELETE("/api/v1/fichas/{ficha_id}", {
      params: { path: { ficha_id: ficha.id } },
    });

    if (error) {
      setErro(extrairErro(error));
      return;
    }
    onExcluida();
  }

  async function depreciar() {
    if (!ficha) return;
    const { error } = await api.POST("/api/v1/fichas/{ficha_id}/depreciar", {
      params: { path: { ficha_id: ficha.id } },
    });
    if (error) {
      setErro(extrairErro(error));
      return;
    }
    setErro(null);
    onExcluida();
  }

  return (
    <li className="flex flex-col gap-2 rounded border border-slate-200 bg-white px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="font-medium text-slate-800">
          {nivel === null ? "Ficha unica (todos os niveis)" : `Nivel ${nivel}`}
        </span>

        {ficha ? (
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
              {ficha.status} · v{ficha.versao}
            </span>
            <Link
              to={`/eventos/${eventoId}/modalidades/${modalidadeId}/fichas/${ficha.id}/editar`}
              className="text-sm font-medium text-slate-700 underline"
            >
              Editar
            </Link>
            <Link
              to={`/eventos/${eventoId}/modalidades/${modalidadeId}/fichas/${ficha.id}/preview`}
              className="text-sm font-medium text-slate-700 underline"
            >
              Preview
            </Link>
            <button
              type="button"
              onClick={excluir}
              className="text-sm font-medium text-red-700 underline"
            >
              Excluir
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => onCriar(nivel)}
            className="rounded bg-slate-800 px-3 py-1.5 text-sm font-medium text-white"
          >
            Criar ficha
          </button>
        )}
      </div>

      {erro && (
        <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
          <p>{erro.mensagem}</p>
          {erro.codigo === "FICHA_POSSUI_LANCAMENTOS" && (
            <button
              type="button"
              onClick={depreciar}
              className="mt-1 font-medium underline"
            >
              Depreciar em vez de excluir
            </button>
          )}
        </div>
      )}
    </li>
  );
}

export function FichaListPage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

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

  const { data: fichas } = useQuery({
    queryKey: ["fichas", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas", {
        params: { query: { modalidade_id: modalidadeId, size: 100 } },
      });
      return data?.itens as FichaResumo[] | undefined;
    },
    enabled: !!modalidadeId,
  });

  async function criarFicha(nivel: number | null) {
    const { data } = await api.POST("/api/v1/fichas", {
      body: { modalidade_id: modalidadeId!, nivel },
    });
    if (data) {
      await queryClient.invalidateQueries({ queryKey: ["fichas", modalidadeId] });
      navigate(`/eventos/${eventoId}/modalidades/${modalidadeId}/fichas/${data.id}/editar`);
    }
  }

  function onExcluida() {
    void queryClient.invalidateQueries({ queryKey: ["fichas", modalidadeId] });
  }

  const slots: (number | null)[] = modalidade?.ficha_unica_entre_niveis
    ? [null]
    : (modalidade?.niveis_aplicaveis ?? []);

  const statusInativos = ["SUBSTITUIDA", "DEPRECADA"];

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">
        Fichas de {modalidade?.nome ?? "..."}
      </h1>

      <ul className="space-y-2">
        {slots.map((nivel) => (
          <SlotFicha
            key={String(nivel)}
            nivel={nivel}
            ficha={fichas?.find((f) => f.nivel === nivel && !statusInativos.includes(f.status))}
            eventoId={eventoId!}
            modalidadeId={modalidadeId!}
            onCriar={criarFicha}
            onExcluida={onExcluida}
          />
        ))}
      </ul>
    </main>
  );
}
