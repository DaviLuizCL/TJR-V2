import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import { PageHeader } from "../../components/PageHeader";
import { TIPOS_REGRA, urlRegra, type ModalidadeComRegras } from "../../lib/regras";

// Pro professor e pro aluno lerem as regras de cada modalidade, sem login.
export function RegrasPublicasPage() {
  const [modalidadeId, setModalidadeId] = useState("");

  const { data: modalidades, isLoading } = useQuery({
    queryKey: ["publico-regras"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/publico/regras");
      return (data ?? []) as ModalidadeComRegras[];
    },
  });

  const comRegra = (modalidades ?? []).filter((m) => m.regras.length > 0);
  const escolhida = comRegra.find((m) => m.id === modalidadeId);

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        sobretitulo="TJR · Regras"
        titulo="Regras das modalidades"
        descricao="Escolha a modalidade pra abrir o manual completo ou o caderninho do aluno."
        voltar={{ para: "/", rotulo: "Início" }}
      />

      {isLoading ? (
        <p className="text-slate-500">Carregando...</p>
      ) : comRegra.length === 0 ? (
        <EmptyState icone="📘" titulo="Nenhuma regra publicada ainda.">
          Assim que a coordenação enviar os PDFs, eles aparecem aqui.
        </EmptyState>
      ) : (
        <>
          <label htmlFor="regra-modalidade" className="mb-1 block text-sm font-medium text-slate-600">
            Modalidade
          </label>
          <select
            id="regra-modalidade"
            value={modalidadeId}
            onChange={(e) => setModalidadeId(e.target.value)}
            className="mb-4 min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2 text-base"
          >
            <option value="">Escolha a modalidade</option>
            {comRegra.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome}
              </option>
            ))}
          </select>

          {escolhida && (
            <div className="grid gap-3 sm:grid-cols-2">
              {TIPOS_REGRA.map(({ tipo, rotulo, descricao }) =>
                escolhida.regras.some((r) => r.tipo === tipo) ? (
                  <a
                    key={tipo}
                    href={urlRegra(escolhida.id, tipo)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary min-h-16 flex-col gap-0 text-lg"
                  >
                    <span>📄 {rotulo}</span>
                    <span className="text-xs font-normal normal-case tracking-normal opacity-80">
                      {descricao}
                    </span>
                  </a>
                ) : (
                  <div
                    key={tipo}
                    className="card flex min-h-16 flex-col items-center justify-center border-dashed p-3 text-center"
                  >
                    <span className="font-semibold text-slate-500">{rotulo}</span>
                    <span className="text-xs text-slate-500">Ainda não disponível</span>
                  </div>
                ),
              )}
            </div>
          )}
        </>
      )}
    </main>
  );
}
