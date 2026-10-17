import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../../api/client";
import type { components } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { PageHeader } from "../../components/PageHeader";
import { Tabs } from "../../components/Tabs";
import { rotuloNivel } from "../../lib/nivel";
import { slug } from "../../lib/slug";

type ModalidadePublica = components["schemas"]["ModalidadePublicaOut"];
type NivelPublico = components["schemas"]["NivelPublicoOut"];
type EquipePublica = components["schemas"]["EquipePublicaOut"];

function ChipRodada({ numero, competiu }: { numero: number; competiu: boolean }) {
  return (
    <span
      className={`chip ${
        competiu
          ? "border-emerald-500/40 bg-emerald-50 text-emerald-700"
          : "border-slate-300 bg-slate-100 text-slate-500"
      }`}
    >
      <span aria-hidden="true">{competiu ? `✓ Rodada ${numero}` : `Rodada ${numero}`}</span>
      <span className="sr-only">
        Rodada {numero}: {competiu ? "já competiu" : "falta competir"}
      </span>
    </span>
  );
}

function LinhaEquipe({ equipe, rodadas }: { equipe: EquipePublica; rodadas: number[] }) {
  return (
    <li
      className={`flex items-center gap-3 rounded-lg border px-3 py-3 ${
        equipe.proxima ? "border-neon/60 bg-slate-100 shadow-glow" : "border-slate-200"
      } ${equipe.presente ? "" : "opacity-60"}`}
    >
      <span
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-display text-lg font-bold ${
          equipe.proxima ? "bg-neon text-slate-50" : "bg-slate-100 text-slate-600 ring-1 ring-slate-200"
        }`}
      >
        {equipe.posicao}º
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span data-nome className="break-words font-semibold text-slate-900">
            {equipe.nome}
          </span>
          {equipe.proxima && (
            <span className="chip border-neon/50 bg-neon/10 text-neon">Próxima</span>
          )}
          {!equipe.presente && (
            <span className="chip border-amber-500/40 bg-amber-50 text-amber-700">Ausente</span>
          )}
          {!!equipe.equipes_na_frente && (
            <span className="text-xs text-slate-500">
              {equipe.equipes_na_frente === 1
                ? "1 equipe na frente"
                : `${equipe.equipes_na_frente} equipes na frente`}
            </span>
          )}
        </div>
        {rodadas.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {rodadas.map((numero) => (
              <ChipRodada
                key={numero}
                numero={numero}
                competiu={equipe.rodadas_competidas.includes(numero)}
              />
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

function SecaoNivel({
  nivel,
  equipes,
  rodadas,
}: {
  nivel: NivelPublico;
  equipes: EquipePublica[];
  rodadas: number[];
}) {
  const rotulo = rotuloNivel(nivel.nivel);
  const idTitulo = `sequencia-nivel-${nivel.nivel}`;
  return (
    <section aria-labelledby={idTitulo} className="card p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={idTitulo} className="text-xl font-bold">
          {rotulo}
        </h2>
        <p className="flex flex-wrap gap-x-3 text-xs text-slate-500">
          {rodadas.map((numero) => (
            <span key={numero}>
              Rodada {numero}:{" "}
              {nivel.equipes.filter((e) => e.rodadas_competidas.includes(numero)).length} de{" "}
              {nivel.equipes.length}
            </span>
          ))}
        </p>
      </div>
      <ol className="space-y-2">
        {equipes.map((equipe) => (
          <LinhaEquipe key={`${equipe.posicao}-${equipe.nome}`} equipe={equipe} rodadas={rodadas} />
        ))}
      </ol>
    </section>
  );
}

export function SequenciaPublicaPage() {
  // Modalidade fica no link pelo nome (/sequencia/danca), pra coordenacao
  // mandar no grupo ja aberto nela. O sistema so tem o evento do TJR.
  const { modalidade: modalidadeNoLink } = useParams<{ modalidade?: string }>();
  const navigate = useNavigate();
  const [busca, setBusca] = useState("");

  const { data: modalidades, isLoading } = useQuery({
    queryKey: ["publico-sequencia"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/publico/sequencia");
      return (data ?? []) as ModalidadePublica[];
    },
    // Fica aberta no celular do professor durante o evento: atualiza sozinha.
    refetchInterval: 30_000,
  });

  const modalidade =
    modalidades?.find((m) => slug(m.nome) === modalidadeNoLink) ?? modalidades?.[0] ?? null;
  const termo = busca.trim().toLowerCase();
  const niveisFiltrados = (modalidade?.niveis ?? [])
    .map((nivel) => ({
      nivel,
      equipes: nivel.equipes.filter((e) => termo === "" || e.nome.toLowerCase().includes(termo)),
    }))
    .filter((item) => item.equipes.length > 0);

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        sobretitulo="TJR · Acompanhe ao vivo"
        titulo="Sequência de competição"
        descricao="Ordem em que as equipes se apresentam em cada modalidade e quem já competiu em cada rodada. A página se atualiza sozinha."
      />

      {isLoading ? (
        <p className="text-slate-500">Carregando...</p>
      ) : !modalidade ? (
        <EmptyState titulo="A sequência de competição ainda não foi divulgada." />
      ) : (
        <>
          <Tabs
            tamanho="pequeno"
            itens={(modalidades ?? []).map((m) => ({ valor: m.id, rotulo: m.nome }))}
            valor={modalidade.id}
            onChange={(id) => {
              const escolhida = modalidades?.find((m) => m.id === id);
              if (escolhida) navigate(`/sequencia/${slug(escolhida.nome)}`, { replace: true });
            }}
          />

          <div className="mb-4">
            <label htmlFor="busca-equipe" className="mb-1 block text-sm font-medium text-slate-600">
              Buscar equipe
            </label>
            <input
              id="busca-equipe"
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Digite o nome da sua equipe"
              className="min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2 text-base"
            />
          </div>

          {niveisFiltrados.length === 0 ? (
            <p className="text-slate-500">
              {termo
                ? "Nenhuma equipe com esse nome nesta modalidade."
                : "Nenhuma equipe inscrita nesta modalidade ainda."}
            </p>
          ) : (
            <div className="space-y-4">
              {niveisFiltrados.map(({ nivel, equipes }) => (
                <SecaoNivel
                  key={nivel.nivel}
                  nivel={nivel}
                  equipes={equipes}
                  rodadas={modalidade.rodadas}
                />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
