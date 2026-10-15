import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Tabs } from "../../components/Tabs";
import { useAuthStore } from "../../lib/auth-store";
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
  // Juiz so pontua: chaveamento e ferramenta da coordenacao.
  const ehArbitro = useAuthStore((state) => state.usuario?.papel) === "ARBITRO";

  if (ehArbitro) return <CombateDashboardPage />;

  return (
    <div>
      <Tabs
        tamanho="pequeno"
        itens={[
          { valor: "modalidades", rotulo: "Modalidades", icone: "📝" },
          { valor: "chaveamento", rotulo: "Chaveamento", icone: "🏆" },
        ]}
        valor={aba}
        onChange={setAba}
      />

      {aba === "modalidades" && <CombateDashboardPage />}
      {aba === "chaveamento" && <ChaveamentoPage />}
    </div>
  );
}
