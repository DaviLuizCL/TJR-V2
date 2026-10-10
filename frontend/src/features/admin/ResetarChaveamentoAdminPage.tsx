import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../../api/client";
import { ResetarChaveamentoModal } from "../chaveamento/ResetarChaveamentoModal";
import { VoltarAdmin } from "./VoltarAdmin";

interface ModalidadeResumo {
  id: string;
  nome: string;
  tipo_disputa: string;
}

export function ResetarChaveamentoAdminPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const [resetando, setResetando] = useState<ModalidadeResumo | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const { data: modalidades, isLoading } = useQuery({
    queryKey: ["modalidades", eventoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades", {
        params: { query: { evento_id: eventoId, size: 100 } },
      });
      return (data?.itens ?? []) as ModalidadeResumo[];
    },
    enabled: !!eventoId,
  });

  const combates = (modalidades ?? []).filter((m) => m.tipo_disputa === "CONFRONTO");

  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-8">
      <VoltarAdmin />
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">Resetar chaveamento</h1>
      <div className="mb-6 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-900">
        <p className="mb-1 font-semibold">⚠️ Use só se o chaveamento foi montado errado.</p>
        <p>
          Apaga <strong>todos</strong> os confrontos, rodadas e notas da modalidade escolhida,
          pra montar de novo do zero. As equipes e inscrições continuam. Uma cópia de tudo que foi
          apagado fica guardada no histórico do sistema, mas não volta pra tela.
        </p>
      </div>

      {aviso && (
        <p className="mb-4 rounded bg-emerald-100 p-3 font-medium text-emerald-900">{aviso}</p>
      )}
      {isLoading && <p className="text-slate-500">Carregando...</p>}

      <ul className="space-y-2">
        {combates.map((modalidade) => (
          <li
            key={modalidade.id}
            className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3"
          >
            <span className="font-medium text-slate-800">{modalidade.nome}</span>
            <button
              type="button"
              onClick={() => {
                setAviso(null);
                setResetando(modalidade);
              }}
              className="min-h-12 rounded border border-red-300 px-4 text-sm font-medium text-red-700"
            >
              Resetar
            </button>
          </li>
        ))}
      </ul>

      {resetando && (
        <ResetarChaveamentoModal
          modalidadeId={resetando.id}
          onFechar={() => setResetando(null)}
          onResetado={() => {
            setAviso(`Chaveamento de ${resetando.nome} apagado. Já pode montar de novo.`);
            setResetando(null);
          }}
        />
      )}
    </main>
  );
}
