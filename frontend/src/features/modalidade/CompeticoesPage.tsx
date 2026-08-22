import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { useEventoStore } from "../../lib/evento-store";
import { ConfrontoHubPage } from "./ConfrontoHubPage";
import { IndividualHubPage } from "./IndividualHubPage";

type Aba = "individual" | "combate";

const ABAS: Aba[] = ["individual", "combate"];

function abaValida(valor: string | null): Aba {
  return ABAS.includes(valor as Aba) ? (valor as Aba) : "individual";
}

export function CompeticoesPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const definirEventoAtual = useEventoStore((state) => state.definirEventoAtual);
  const [searchParams] = useSearchParams();
  const [aba, setAba] = useState<Aba>(abaValida(searchParams.get("aba")));

  // Competicoes e o destino padrao ao clicar num evento (EventoSelectPage) -
  // sem isso, quem chega direto aqui nunca passa por ModalidadeListPage, e
  // os outros links do Header (Painel, Modalidades, Fichas) ficam sem saber
  // qual e o evento atual, caindo de volta pra /eventos.
  useEffect(() => {
    if (eventoId) definirEventoAtual(eventoId);
  }, [eventoId, definirEventoAtual]);

  function classesAba(valor: Aba): string {
    return `min-h-12 rounded-t px-4 py-2 text-sm font-medium ${
      aba === valor ? "border-b-2 border-slate-800 text-slate-900" : "text-slate-500"
    }`;
  }

  return (
    <main className="mx-auto max-w-6xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Competições</h1>

      <div role="tablist" className="mb-6 flex gap-2 border-b border-slate-200">
        <button
          role="tab"
          type="button"
          aria-selected={aba === "individual"}
          onClick={() => setAba("individual")}
          className={classesAba("individual")}
        >
          Individual
        </button>
        <button
          role="tab"
          type="button"
          aria-selected={aba === "combate"}
          onClick={() => setAba("combate")}
          className={classesAba("combate")}
        >
          Combate
        </button>
      </div>

      {aba === "individual" && <IndividualHubPage />}
      {aba === "combate" && <ConfrontoHubPage />}
    </main>
  );
}
