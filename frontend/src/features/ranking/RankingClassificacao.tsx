import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../api/client";

export interface ModalidadeAba {
  id: string;
  nome: string;
}

interface ClassificacaoItem {
  equipe_id: string;
  equipe_nome: string;
  equipe_nivel?: number | null;
  nota_final: number;
  vitorias?: number;
  empates?: number;
  derrotas?: number;
  eliminado_por_nome?: string | null;
  posicao: number;
}

interface RankingModalidade {
  modalidade_id: string;
  modalidade_nome: string;
  tipo_disputa?: string;
  formato_chaveamento?: string | null;
  ranking_liberado: boolean;
  itens: ClassificacaoItem[];
}

export function RankingClassificacao({
  modalidades,
  mensagemVazia,
}: {
  modalidades: ModalidadeAba[] | undefined;
  mensagemVazia: string;
}) {
  const [modalidadeSelecionada, setModalidadeSelecionada] = useState<string | null>(null);
  const abaAtiva = modalidadeSelecionada ?? modalidades?.[0]?.id;

  const { data: ranking } = useQuery({
    queryKey: ["ranking", abaAtiva],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/ranking/modalidades/{modalidade_id}", {
        params: { path: { modalidade_id: abaAtiva! } },
      });
      return data as RankingModalidade | undefined;
    },
    enabled: !!abaAtiva,
  });

  if (!modalidades) return null;

  if (modalidades.length === 0) {
    return <p className="text-slate-500">{mensagemVazia}</p>;
  }

  return (
    <>
      <div role="tablist" className="mb-6 flex flex-wrap gap-2 border-b border-slate-200">
        {modalidades.map((modalidade) => (
          <button
            key={modalidade.id}
            role="tab"
            type="button"
            aria-selected={modalidade.id === abaAtiva}
            onClick={() => setModalidadeSelecionada(modalidade.id)}
            className={`min-h-12 rounded-t px-4 py-2 text-sm font-medium ${
              modalidade.id === abaAtiva
                ? "border-b-2 border-slate-800 text-slate-900"
                : "text-slate-500"
            }`}
          >
            {modalidade.nome}
          </button>
        ))}
      </div>

      {ranking &&
        (() => {
          const formato = ranking.formato_chaveamento;
          const ehMataMata = formato === "MATA_MATA";
          const ehTodosContraTodos = formato === "TODOS_CONTRA_TODOS";

          const gruposPorNivel: Array<[number | null, ClassificacaoItem[]]> = [];
          for (const item of ranking.itens) {
            const nivel = item.equipe_nivel ?? null;
            const grupo = gruposPorNivel.find(([n]) => n === nivel);
            if (grupo) {
              grupo[1].push(item);
            } else {
              gruposPorNivel.push([nivel, [item]]);
            }
          }
          const temMaisDeUmNivel = gruposPorNivel.length > 1;

          return (
            <div className="flex flex-col gap-8">
              {gruposPorNivel.map(([nivel, itens]) => (
                <div key={String(nivel)}>
                  {temMaisDeUmNivel && (
                    <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600">
                      Nível {nivel}
                    </h3>
                  )}
                  <table className="w-full text-left">
                    <thead>
                      <tr className="text-sm uppercase tracking-wide text-slate-500">
                        <th className="py-2">Posicao</th>
                        <th className="py-2">Equipe</th>
                        {ehMataMata ? (
                          <>
                            <th className="py-2">Vitorias</th>
                            <th className="py-2">Derrotas</th>
                            <th className="py-2">Eliminado por</th>
                          </>
                        ) : ehTodosContraTodos ? (
                          <>
                            <th className="py-2">Vitorias</th>
                            <th className="py-2">Empates</th>
                            <th className="py-2">Derrotas</th>
                            <th className="py-2">Pontos</th>
                          </>
                        ) : (
                          <th className="py-2">Nota</th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {itens.map((item) => {
                        return (
                          <tr key={item.equipe_id} className="border-t border-slate-100">
                            <td className="py-2 font-semibold text-slate-800">{item.posicao}º</td>
                            <td className="py-2 text-slate-800">{item.equipe_nome}</td>
                            {ehMataMata ? (
                              <>
                                <td className="py-2 text-slate-800">{item.vitorias ?? 0}</td>
                                <td className="py-2 text-slate-800">{item.derrotas ?? 0}</td>
                                <td className="py-2 text-slate-800">
                                  {item.eliminado_por_nome ?? "-"}
                                </td>
                              </>
                            ) : ehTodosContraTodos ? (
                              <>
                                <td className="py-2 text-slate-800">{item.vitorias ?? 0}</td>
                                <td className="py-2 text-slate-800">{item.empates ?? 0}</td>
                                <td className="py-2 text-slate-800">{item.derrotas ?? 0}</td>
                                <td className="py-2 text-slate-800">{item.nota_final}</td>
                              </>
                            ) : (
                              <td className="py-2 text-slate-800">{item.nota_final}</td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          );
        })()}
    </>
  );
}
