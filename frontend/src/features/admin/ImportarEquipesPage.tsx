import { useState } from "react";
import { useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { VoltarAdmin } from "./VoltarAdmin";

interface Relatorio {
  simulacao: boolean;
  linhas: number;
  equipes_novas: number;
  inscricoes_novas: number;
  ignoradas: number;
  erros: string[];
}

function ResumoRelatorio({ relatorio }: { relatorio: Relatorio }) {
  return (
    <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4">
      <ul className="mb-2 space-y-1 text-slate-800">
        <li>📄 {relatorio.linhas} linhas na planilha</li>
        <li>👥 {relatorio.equipes_novas} equipes novas</li>
        <li>📝 {relatorio.inscricoes_novas} inscrições novas</li>
        <li className="text-slate-500">
          {relatorio.ignoradas} linhas ignoradas (linha de teste ou desafio que não existe no
          sistema)
        </li>
      </ul>
      {relatorio.erros.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="mb-1 font-semibold">
            ⚠️ {relatorio.erros.length} linha(s) com problema — essas não entram:
          </p>
          <ul className="list-disc pl-5">
            {relatorio.erros.map((erro) => (
              <li key={erro}>{erro}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function ImportarEquipesPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<Relatorio | null>(null);
  const [concluido, setConcluido] = useState<Relatorio | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar(simular: boolean): Promise<Relatorio | null> {
    if (!arquivo) return null;
    const formulario = new FormData();
    formulario.append("arquivo", arquivo);
    setEnviando(true);
    setErro(null);
    const { data, error } = await api.POST("/api/v1/admin/importar-equipes", {
      params: { query: { evento_id: eventoId!, simular } },
      body: formulario as never,
    });
    setEnviando(false);
    if (error || !data) {
      setErro(extrairErro(error).mensagem);
      return null;
    }
    return data as Relatorio;
  }

  async function verPrevia() {
    setConcluido(null);
    setPrevia(await enviar(true));
  }

  async function confirmar() {
    const resultado = await enviar(false);
    if (resultado) {
      setPrevia(null);
      setConcluido(resultado);
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-8">
      <VoltarAdmin />
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">Importar equipes da planilha</h1>
      <div className="mb-6 text-sm text-slate-500">
        <p className="mb-1">
          Use a planilha oficial de inscrições (.xlsx). O sistema lê a coluna A (desafio), B
          (nível) e E (nome da equipe).
        </p>
        <p>
          Nada é apagado: equipe que já existe com o mesmo nome e nível é reaproveitada, e
          inscrição repetida é pulada. Pode importar de novo sem medo de duplicar.
        </p>
      </div>

      <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4">
        <label className="mb-2 block font-medium text-slate-700" htmlFor="planilha">
          1. Escolha a planilha
        </label>
        <input
          id="planilha"
          type="file"
          accept=".xlsx"
          onChange={(e) => {
            setArquivo(e.target.files?.[0] ?? null);
            setPrevia(null);
            setConcluido(null);
            setErro(null);
          }}
          className="mb-3 block w-full text-sm"
        />
        <button
          type="button"
          onClick={verPrevia}
          disabled={!arquivo || enviando}
          className="min-h-12 rounded bg-slate-800 px-4 font-medium text-white disabled:opacity-50"
        >
          {enviando && !previa ? "Lendo..." : "2. Ver prévia"}
        </button>
        <p className="mt-1 text-xs text-slate-500">
          A prévia mostra o que vai acontecer, sem gravar nada ainda.
        </p>
      </div>

      {erro && <p className="mb-4 rounded bg-red-50 p-3 font-medium text-red-700">{erro}</p>}

      {previa && (
        <>
          <h2 className="mb-2 text-lg font-semibold text-slate-800">Prévia (nada gravado ainda)</h2>
          <ResumoRelatorio relatorio={previa} />
          <button
            type="button"
            onClick={confirmar}
            disabled={enviando}
            className="min-h-12 rounded bg-emerald-700 px-4 font-medium text-white disabled:opacity-50"
          >
            {enviando ? "Importando..." : "3. Confirmar importação"}
          </button>
        </>
      )}

      {concluido && (
        <>
          <p className="mb-2 rounded bg-emerald-100 p-3 font-semibold text-emerald-900">
            ✅ Importação concluída.
          </p>
          <ResumoRelatorio relatorio={concluido} />
        </>
      )}
    </main>
  );
}
