import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../api/client";
import type { components } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { PageHeader } from "../../components/PageHeader";
import { rotuloNivel } from "../../lib/nivel";

type EquipeInscrita = components["schemas"]["EquipeInscritaPublicaOut"];

function CartaoEquipe({ equipe }: { equipe: EquipeInscrita }) {
  const total = equipe.modalidades.length;
  return (
    <li className="rounded-lg border border-slate-200 px-3 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="break-words font-semibold text-slate-900">{equipe.nome}</span>
        {total > 1 && <span className="text-xs text-slate-500">{total} modalidades</span>}
      </div>
      {total === 0 ? (
        <p className="mt-1.5 text-sm text-amber-700">
          Não está em nenhuma modalidade. Avise a coordenação.
        </p>
      ) : (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {equipe.modalidades.map((modalidade) => (
            <span key={modalidade} className="chip border-plasma/40 bg-plasma/10 text-plasma">
              {modalidade}
            </span>
          ))}
        </div>
      )}
    </li>
  );
}

function SecaoNivel({ nivel, equipes }: { nivel: number; equipes: EquipeInscrita[] }) {
  const idTitulo = `equipes-nivel-${nivel}`;
  return (
    <section aria-labelledby={idTitulo} className="card p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={idTitulo} className="text-xl font-bold">
          {rotuloNivel(nivel)}
        </h2>
        <span className="text-xs text-slate-500">
          {equipes.length === 1 ? "1 equipe" : `${equipes.length} equipes`}
        </span>
      </div>
      <ul className="space-y-2">
        {equipes.map((equipe, indice) => (
          <CartaoEquipe key={`${indice}-${equipe.nome}`} equipe={equipe} />
        ))}
      </ul>
    </section>
  );
}

// Pro professor conferir o cadastro antes do evento: nome, nivel e em quais
// modalidades cada equipe esta. Sem login e sem nota.
export function EquipesPublicasPage() {
  const [busca, setBusca] = useState("");
  const [modalidade, setModalidade] = useState("");

  const { data: equipes, isLoading } = useQuery({
    queryKey: ["publico-equipes"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/publico/equipes");
      return (data ?? []) as EquipeInscrita[];
    },
  });

  const modalidades = [...new Set((equipes ?? []).flatMap((e) => e.modalidades))].sort((a, b) =>
    a.localeCompare(b, "pt-BR"),
  );
  const termo = busca.trim().toLowerCase();
  const filtradas = (equipes ?? []).filter(
    (e) =>
      (termo === "" || e.nome.toLowerCase().includes(termo)) &&
      (modalidade === "" || e.modalidades.includes(modalidade)),
  );
  // A API ja manda ordenado por nivel e nome.
  const niveis = [...new Set(filtradas.map((e) => e.nivel))];

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        sobretitulo="TJR · Confira o cadastro"
        titulo="Equipes inscritas"
        descricao="Confira o nome, o nível e as modalidades de cada equipe. Se algo estiver errado, avise a coordenação antes do evento."
        voltar={{ para: "/", rotulo: "Início" }}
      />

      {isLoading ? (
        <p className="text-slate-500">Carregando...</p>
      ) : !equipes || equipes.length === 0 ? (
        <EmptyState titulo="Nenhuma equipe cadastrada ainda." />
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            <div>
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
            <div>
              <label
                htmlFor="filtro-modalidade"
                className="mb-1 block text-sm font-medium text-slate-600"
              >
                Modalidade
              </label>
              <select
                id="filtro-modalidade"
                value={modalidade}
                onChange={(e) => setModalidade(e.target.value)}
                className="min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2 text-base"
              >
                <option value="">Todas</option>
                {modalidades.map((nome) => (
                  <option key={nome} value={nome}>
                    {nome}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {niveis.length === 0 ? (
            <p className="text-slate-500">Nenhuma equipe encontrada com esse filtro.</p>
          ) : (
            <div className="space-y-4">
              {niveis.map((nivel) => (
                <SecaoNivel
                  key={nivel}
                  nivel={nivel}
                  equipes={filtradas.filter((e) => e.nivel === nivel)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
