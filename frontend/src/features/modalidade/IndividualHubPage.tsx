import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { HorarioDashboardPage } from "../horario/HorarioDashboardPage";
import { PontuarDashboardPage } from "../arbitragem/PontuarDashboardPage";

type Aba = "pontuar" | "horarios";

const ABAS: Aba[] = ["pontuar", "horarios"];

function abaValida(valor: string | null): Aba {
  return ABAS.includes(valor as Aba) ? (valor as Aba) : "pontuar";
}

export function IndividualHubPage() {
  const [searchParams] = useSearchParams();
  const [aba, setAba] = useState<Aba>(abaValida(searchParams.get("sub")));

  function classesAba(valor: Aba): string {
    return `min-h-12 rounded-t px-4 py-2 text-sm font-medium ${
      aba === valor ? "border-b-2 border-slate-800 text-slate-900" : "text-slate-500"
    }`;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div role="tablist" className="mb-6 flex gap-2 border-b border-slate-200">
        <button
          role="tab"
          type="button"
          aria-selected={aba === "pontuar"}
          onClick={() => setAba("pontuar")}
          className={classesAba("pontuar")}
        >
          Pontuar
        </button>
        <button
          role="tab"
          type="button"
          aria-selected={aba === "horarios"}
          onClick={() => setAba("horarios")}
          className={classesAba("horarios")}
        >
          Horários
        </button>
      </div>

      {aba === "pontuar" && <PontuarDashboardPage />}
      {aba === "horarios" && <HorarioDashboardPage />}
    </div>
  );
}
