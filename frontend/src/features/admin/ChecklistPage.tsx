import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { VoltarAdmin } from "./VoltarAdmin";

interface ItemChecklist {
  codigo: string;
  ok: boolean;
  mensagem: string;
}

interface SecaoModalidade {
  modalidade_id: string;
  nome: string;
  tipo_disputa: string;
  itens: ItemChecklist[];
}

interface Checklist {
  gerais: ItemChecklist[];
  modalidades: SecaoModalidade[];
}

// Pra onde o botao "Resolver" leva, por codigo de item (estavel, vem do backend).
function linkResolver(eventoId: string, codigo: string, modalidadeId?: string): string | null {
  const base = `/eventos/${eventoId}/modalidades/${modalidadeId}`;
  switch (codigo) {
    case "FICHA":
      return `${base}/fichas`;
    case "EQUIPES":
      return `${base}/inscricoes`;
    case "RODADAS":
    case "CONFRONTOS":
      return `${base}/rodadas`;
    case "ORDEM":
      return `${base}/ordem`;
    case "JUIZES":
      return "/usuarios";
    case "NOTAS_PENDENTES":
      return `/eventos/${eventoId}/admin/corrigir`;
    default:
      return null;
  }
}

function ListaItens({
  itens,
  eventoId,
  modalidadeId,
}: {
  itens: ItemChecklist[];
  eventoId: string;
  modalidadeId?: string;
}) {
  return (
    <ul className="space-y-2">
      {itens.map((item) => {
        const link = item.ok ? null : linkResolver(eventoId, item.codigo, modalidadeId);
        return (
          <li
            key={item.codigo}
            className={`flex items-center gap-3 rounded border px-3 py-2 ${
              item.ok ? "border-emerald-200 bg-emerald-50" : "border-amber-300 bg-amber-50"
            }`}
          >
            <span aria-hidden="true" className="text-xl">
              {item.ok ? "✅" : "⚠️"}
            </span>
            <span className={`flex-1 ${item.ok ? "text-emerald-900" : "text-amber-900"}`}>
              {item.mensagem}
            </span>
            {link && (
              <Link
                to={link}
                className="flex min-h-12 items-center rounded bg-amber-700 px-4 text-sm font-medium text-white"
              >
                Resolver →
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function ChecklistPage() {
  const { eventoId } = useParams<{ eventoId: string }>();

  const { data: checklist, isLoading } = useQuery({
    queryKey: ["admin-checklist", eventoId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/admin/checklist", {
        params: { query: { evento_id: eventoId! } },
      });
      return data as Checklist | undefined;
    },
    enabled: !!eventoId,
  });

  const pendencias = checklist
    ? [...checklist.gerais, ...checklist.modalidades.flatMap((m) => m.itens)].filter((i) => !i.ok)
        .length
    : 0;

  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-8">
      <VoltarAdmin />
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">Checklist do dia</h1>
      <p className="mb-6 text-sm text-slate-500">
        Confere se cada modalidade está pronta pra começar. Onde tiver ⚠️, clique em
        "Resolver" pra ir direto pra tela que arruma.
      </p>

      {isLoading && <p className="animate-pulse text-slate-500">Carregando...</p>}

      {checklist && (
        <>
          <div
            className={`mb-6 rounded-lg p-4 text-lg font-semibold ${
              pendencias === 0 ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"
            }`}
          >
            {pendencias === 0
              ? "✅ Tudo pronto!"
              : `⚠️ ${pendencias} ${pendencias === 1 ? "pendência" : "pendências"} pra resolver`}
          </div>

          <section className="mb-6">
            <h2 className="mb-2 text-lg font-semibold text-slate-800">Geral</h2>
            <ListaItens itens={checklist.gerais} eventoId={eventoId!} />
          </section>

          {checklist.modalidades.map((secao) => (
            <section key={secao.modalidade_id} className="mb-6">
              <h2 className="mb-2 text-lg font-semibold text-slate-800">
                {secao.nome}
                <span className="ml-2 text-sm font-normal text-slate-500">
                  {secao.tipo_disputa === "CONFRONTO" ? "combate" : "individual"}
                </span>
              </h2>
              <ListaItens
                itens={secao.itens}
                eventoId={eventoId!}
                modalidadeId={secao.modalidade_id}
              />
            </section>
          ))}
        </>
      )}
    </main>
  );
}
