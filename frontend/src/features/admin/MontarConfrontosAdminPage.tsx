import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../../api/client";
import { ChaveamentoManualBuilder } from "../modalidade/ChaveamentoManualBuilder";
import { VoltarAdmin } from "./VoltarAdmin";

interface ModalidadeResumo {
  id: string;
  nome: string;
  tipo_disputa: string;
}

export function MontarConfrontosAdminPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const [escolhida, setEscolhida] = useState<ModalidadeResumo | null>(null);

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
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <VoltarAdmin />
      {escolhida ? (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-3xl font-bold">Confrontos de {escolhida.nome}</h1>
            <button
              type="button"
              onClick={() => setEscolhida(null)}
              className="btn-secondary min-h-12 text-sm"
            >
              Trocar modalidade
            </button>
          </div>
          <ChaveamentoManualBuilder key={escolhida.id} modalidadeId={escolhida.id} comoPagina />
        </>
      ) : (
        <>
          <h1 className="mb-2 text-3xl font-bold">Montar confrontos</h1>
          <p className="mb-6 text-slate-500">
            Escolha a modalidade de combate. Cada confronto salvo já vira um card pro juiz pontuar.
          </p>
          {isLoading && <p className="text-slate-500">Carregando...</p>}
          <ul className="space-y-2">
            {combates.map((modalidade) => (
              <li key={modalidade.id}>
                <button
                  type="button"
                  onClick={() => setEscolhida(modalidade)}
                  className="card min-h-12 w-full px-4 py-3 text-left font-medium text-slate-800"
                >
                  {modalidade.nome}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
