import { useState } from "react";

import { api, extrairErro } from "../../api/client";

export function ResetarChaveamentoModal({
  modalidadeId,
  onFechar,
  onResetado,
}: {
  modalidadeId: string;
  onFechar: () => void;
  onResetado: () => void;
}) {
  const [justificativa, setJustificativa] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    const { error } = await api.POST("/api/v1/modalidades/{modalidade_id}/chaveamento/reset", {
      params: { path: { modalidade_id: modalidadeId } },
      body: { justificativa: justificativa.trim() },
    });
    setEnviando(false);

    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }

    onResetado();
  }

  return (
    <div
      role="dialog"
      aria-label="Resetar chaveamento"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-1 text-lg font-semibold text-slate-800">Resetar chaveamento</h2>
        <p className="mb-4 text-sm text-slate-500">
          Apaga de verdade todas as rodadas, partidas e lançamentos já feitos nessa modalidade,
          pra recomeçar o chaveamento do zero (ex.: formato errado configurado por engano). Essa
          ação não pode ser desfeita.
        </p>

        <label
          htmlFor="justificativa-reset-chaveamento"
          className="mb-1 block text-sm font-medium text-slate-700"
        >
          Justificativa
        </label>
        <textarea
          id="justificativa-reset-chaveamento"
          value={justificativa}
          onChange={(e) => setJustificativa(e.target.value)}
          disabled={enviando}
          rows={3}
          className="mb-4 w-full rounded border border-slate-300 px-3 py-2 text-sm"
        />

        {erro && <p className="mb-4 text-sm text-red-600">{erro}</p>}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onFechar}
            disabled={enviando}
            className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={confirmar}
            disabled={enviando || justificativa.trim().length === 0}
            className="rounded bg-red-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {enviando ? "Resetando..." : "Confirmar reset"}
          </button>
        </div>
      </div>
    </div>
  );
}
