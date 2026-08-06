import { useState } from "react";

import type { ModalidadeAba } from "../ranking/RankingClassificacao";
import { ListaSubmissoes } from "./ListaSubmissoes";

export function SubmissoesTab({
  eventoId,
  modalidades,
}: {
  eventoId: string;
  modalidades: ModalidadeAba[] | undefined;
}) {
  const [modalidadeFiltro, setModalidadeFiltro] = useState("");

  return (
    <div>
      {modalidades && modalidades.length > 1 && (
        <div className="mb-4">
          <label
            className="mb-1 block text-sm font-medium text-slate-700"
            htmlFor="filtro-modalidade-submissoes"
          >
            Filtrar por modalidade
          </label>
          <select
            id="filtro-modalidade-submissoes"
            value={modalidadeFiltro}
            onChange={(e) => setModalidadeFiltro(e.target.value)}
            className="w-full max-w-xs rounded border border-slate-300 px-3 py-2"
          >
            <option value="">Todas as modalidades</option>
            {modalidades.map((modalidade) => (
              <option key={modalidade.id} value={modalidade.id}>
                {modalidade.nome}
              </option>
            ))}
          </select>
        </div>
      )}

      <ListaSubmissoes
        eventoId={eventoId}
        modalidadeId={modalidadeFiltro || undefined}
        mensagemVazia="Nenhuma submissao ainda."
      />
    </div>
  );
}
