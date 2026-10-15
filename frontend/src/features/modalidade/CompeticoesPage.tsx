import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { PageHeader } from "../../components/PageHeader";
import { Tabs } from "../../components/Tabs";
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

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        sobretitulo="TJR 2026"
        titulo="Competições"
        descricao="Escolha o tipo de prova e depois a modalidade que você vai pontuar."
      />

      <Tabs
        itens={[
          { valor: "individual", rotulo: "Individual", icone: "🎯" },
          { valor: "combate", rotulo: "Combate", icone: "⚔️" },
        ]}
        valor={aba}
        onChange={setAba}
      />

      {aba === "individual" && <IndividualHubPage />}
      {aba === "combate" && <ConfrontoHubPage />}
    </main>
  );
}
