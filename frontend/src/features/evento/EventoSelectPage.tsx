import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../../api/client";

// O sistema so suporta um evento por vez (TJR 2026) -- criar evento pelo
// front foi desativado de proposito (backend recusa um segundo evento com
// 422 EVENTO_UNICO_JA_EXISTE), entao esta tela so lista o(s) evento(s)
// existente(s) e navega pra ele.
export function EventoSelectPage() {
  // Clicar no evento leva direto pro fluxo operacional (Competicoes), pra
  // qualquer papel -- area administrativa (Modalidades/Fichas/Equipes)
  // continua acessivel pelo Header pra quem tem permissao.
  function destinoDoEvento(eventoId: string): string {
    return `/eventos/${eventoId}/competicoes`;
  }

  const { data, isLoading } = useQuery({
    queryKey: ["eventos"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/eventos", { params: { query: { size: 50 } } });
      return data?.itens ?? [];
    },
  });

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Eventos</h1>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Selecionar um evento
        </h2>
        {isLoading && <p className="text-slate-500">Carregando...</p>}
        {!isLoading && data?.length === 0 && (
          <p className="text-slate-500">Nenhum evento cadastrado ainda.</p>
        )}
        <ul className="space-y-2">
          {data?.map((evento) => (
            <li key={evento.id}>
              <Link
                to={destinoDoEvento(evento.id)}
                className="block rounded border border-slate-200 bg-white px-4 py-3 hover:border-slate-400"
              >
                <span className="font-medium text-slate-800">{evento.nome}</span>
                <span className="ml-2 text-sm text-slate-500">
                  {evento.ano} · {evento.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
