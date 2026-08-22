import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ChaveamentoPage } from "../chaveamento/ChaveamentoPage";
import { CombateDashboardPage } from "./CombateDashboardPage";

type Aba = "modalidades" | "chaveamento";

const ABAS: Aba[] = ["modalidades", "chaveamento"];

function abaValida(valor: string | null): Aba {
  return ABAS.includes(valor as Aba) ? (valor as Aba) : "modalidades";
}

export function ConfrontoHubPage() {
  const [searchParams] = useSearchParams();
  const [aba, setAba] = useState<Aba>(abaValida(searchParams.get("sub")));

  function classesAba(valor: Aba): string {
    return `min-h-12 rounded-t px-4 py-2 text-sm font-medium ${
      aba === valor ? "border-b-2 border-slate-800 text-slate-900" : "text-slate-500"
    }`;
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div role="tablist" className="mb-6 flex gap-2 border-b border-slate-200">
        <button
          role="tab"
          type="button"
          aria-selected={aba === "modalidades"}
          onClick={() => setAba("modalidades")}
          className={classesAba("modalidades")}
        >
          Modalidades
        </button>
        <button
          role="tab"
          type="button"
          aria-selected={aba === "chaveamento"}
          onClick={() => setAba("chaveamento")}
          className={classesAba("chaveamento")}
        >
          Chaveamento
        </button>
      </div>

      {aba === "modalidades" && <CombateDashboardPage />}
      {aba === "chaveamento" && <ChaveamentoPage />}
    </div>
  );
}
