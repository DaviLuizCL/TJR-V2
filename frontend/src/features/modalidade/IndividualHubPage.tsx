import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { HorarioDashboardPage } from "../horario/HorarioDashboardPage";
import { PontuarDashboardPage } from "../arbitragem/PontuarDashboardPage";
import { RodadaDashboardPage } from "./RodadaDashboardPage";

type Aba = "pontuar" | "rodadas" | "horarios";

const ABAS: Aba[] = ["pontuar", "rodadas", "horarios"];

function abaValida(valor: string | null): Aba {
  return ABAS.includes(valor as Aba) ? (valor as Aba) : "pontuar";
}

export function IndividualHubPage() {
  const [searchParams] = useSearchParams();
  const [aba, setAba] = useState<Aba>(abaValida(searchParams.get("aba")));

  function classesAba(valor: Aba): string {
    return `min-h-12 rounded-t px-4 py-2 text-sm font-medium ${
      aba === valor ? "border-b-2 border-slate-800 text-slate-900" : "text-slate-500"
    }`;
  }

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Individual</h1>

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
          aria-selected={aba === "rodadas"}
          onClick={() => setAba("rodadas")}
          className={classesAba("rodadas")}
        >
          Rodadas
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
      {aba === "rodadas" && <RodadaDashboardPage />}
      {aba === "horarios" && <HorarioDashboardPage />}
    </main>
  );
}
