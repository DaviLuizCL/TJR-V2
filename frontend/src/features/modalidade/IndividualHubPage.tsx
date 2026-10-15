import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Tabs } from "../../components/Tabs";
import { useAuthStore } from "../../lib/auth-store";
import { PontuarDashboardPage } from "../arbitragem/PontuarDashboardPage";
import { OrdemDashboardPage } from "../ordem/OrdemDashboardPage";

type Aba = "pontuar" | "ordem";

const ABAS: Aba[] = ["pontuar", "ordem"];

function abaValida(valor: string | null): Aba {
  return ABAS.includes(valor as Aba) ? (valor as Aba) : "pontuar";
}

export function IndividualHubPage() {
  const [searchParams] = useSearchParams();
  const [aba, setAba] = useState<Aba>(abaValida(searchParams.get("sub")));
  // Juiz so pontua: sequência e ferramenta da coordenacao.
  const ehArbitro = useAuthStore((state) => state.usuario?.papel) === "ARBITRO";

  if (ehArbitro) return <PontuarDashboardPage />;

  return (
    <div>
      <Tabs
        tamanho="pequeno"
        itens={[
          { valor: "pontuar", rotulo: "Pontuar", icone: "📝" },
          { valor: "ordem", rotulo: "Sequência de competição", icone: "🔢" },
        ]}
        valor={aba}
        onChange={setAba}
      />

      {aba === "pontuar" && <PontuarDashboardPage />}
      {aba === "ordem" && <OrdemDashboardPage />}
    </div>
  );
}
