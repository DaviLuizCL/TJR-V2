import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { PageHeader } from "../../components/PageHeader";
import { useEventoStore } from "../../lib/evento-store";

interface Cartao {
  icone: string;
  titulo: string;
  descricao: string;
  destino: string;
  selo?: string;
}

function cartoes(
  eventoId: string,
  pedidosAcesso: number,
): { secao: string; itens: Cartao[] }[] {
  const evento = `/eventos/${eventoId}`;
  return [
    {
      secao: "No dia do evento",
      itens: [
        {
          icone: "✅",
          titulo: "Checklist do dia",
          descricao: "Confere se cada modalidade está pronta e mostra o que falta arrumar.",
          destino: `${evento}/admin/checklist`,
        },
        {
          icone: "✏️",
          titulo: "Corrigir pontuação",
          descricao: "Juiz errou? Ache a nota da equipe e corrija ou anule.",
          destino: `${evento}/admin/corrigir`,
        },
        {
          icone: "🥊",
          titulo: "Montar confrontos",
          descricao: "Escolhe quem enfrenta quem nas modalidades de combate, rodada por rodada.",
          destino: `${evento}/admin/montar-confrontos`,
        },
        {
          icone: "🔢",
          titulo: "Sequência de competição",
          descricao: "Sorteia a ordem das equipes (individuais) e gera o PDF pro telão.",
          destino: `${evento}/competicoes?aba=individual&sub=ordem`,
        },
        {
          icone: "🙋",
          titulo: "Equipes e presença",
          descricao: "Marcar equipe ausente, renomear, mudar de modalidade.",
          destino: "/equipes",
        },
        {
          icone: "📣",
          titulo: "Página dos professores",
          descricao: `Aberta, sem senha: quem já competiu e quem é a próxima. Mande este endereço no grupo: ${window.location.origin}/sequencia`,
          destino: "/sequencia",
        },
      ],
    },
    {
      secao: "Preparação",
      itens: [
        {
          icone: "🔑",
          titulo: "Juízes e senhas",
          descricao: "Aprovar pedido de acesso, cadastrar juiz, trocar senha esquecida, desativar conta.",
          destino: "/usuarios",
          selo:
            pedidosAcesso === 1
              ? "1 pedido de acesso esperando"
              : pedidosAcesso > 1
                ? `${pedidosAcesso} pedidos de acesso esperando`
                : undefined,
        },
        {
          icone: "📥",
          titulo: "Importar equipes",
          descricao: "Sobe a planilha de inscrições e cadastra as equipes de uma vez.",
          destino: `${evento}/admin/importar`,
        },
        {
          icone: "♻️",
          titulo: "Resetar chaveamento",
          descricao: "Apaga os confrontos de uma modalidade de combate pra montar de novo.",
          destino: `${evento}/admin/resetar-chaveamento`,
        },
      ],
    },
  ];
}

function baixarArquivo(conteudo: Blob, nome: string) {
  const url = URL.createObjectURL(conteudo);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  link.click();
  URL.revokeObjectURL(url);
}

function nomeBackup(): string {
  const agora = new Date();
  const doisDigitos = (n: number) => String(n).padStart(2, "0");
  return `tjr-backup-${agora.getFullYear()}-${doisDigitos(agora.getMonth() + 1)}-${doisDigitos(agora.getDate())}-${doisDigitos(agora.getHours())}${doisDigitos(agora.getMinutes())}.dump`;
}

export function AdminPage() {
  const { eventoId } = useParams<{ eventoId: string }>();
  const definirEventoAtual = useEventoStore((state) => state.definirEventoAtual);
  const [baixando, setBaixando] = useState<"backup" | "relatorio" | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const { data: pedidosAcesso } = useQuery({
    queryKey: ["solicitacoes-acesso"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/solicitacoes-acesso");
      return Array.isArray(data) ? data : [];
    },
  });

  useEffect(() => {
    if (eventoId) definirEventoAtual(eventoId);
  }, [eventoId, definirEventoAtual]);

  async function baixarBackup() {
    setBaixando("backup");
    setAviso(null);
    setErro(null);
    const { data, error } = await api.GET("/api/v1/admin/backup", { parseAs: "blob" });
    setBaixando(null);
    if (error || !data) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    baixarArquivo(data as Blob, nomeBackup());
    setAviso("Backup baixado. Guarde o arquivo num pendrive ou na nuvem.");
  }

  async function baixarRelatorio() {
    setBaixando("relatorio");
    setAviso(null);
    setErro(null);
    const { data, error } = await api.GET(
      "/api/v1/ranking/eventos/{evento_id}/relatorio-auditoria.pdf",
      { params: { path: { evento_id: eventoId! } }, parseAs: "blob" },
    );
    setBaixando(null);
    if (error || !data) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    baixarArquivo(data as Blob, "relatorio-geral.pdf");
    setAviso("Relatório baixado.");
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        sobretitulo="Coordenação"
        titulo="Administração"
        descricao="Tudo que o coordenador precisa pra tocar o evento. Em dúvida, comece pelo checklist do dia."
      />

      {cartoes(eventoId!, pedidosAcesso?.length ?? 0).map(({ secao, itens }) => (
        <section key={secao} className="mb-8">
          <h2 className="eyebrow mb-3">
            {secao}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {itens.map((cartao, indice) => (
              <Link
                key={cartao.titulo}
                to={cartao.destino}
                className={`card group flex min-h-24 items-start gap-4 p-5 hover:border-neon/60 hover:shadow-glow ${
                  secao === "No dia do evento" && indice === 0 ? "border-neon/50 sm:col-span-2" : ""
                }`}
              >
                <span
                  aria-hidden="true"
                  className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-slate-100 text-3xl ring-1 ring-slate-200 group-hover:ring-neon/40"
                >
                  {cartao.icone}
                </span>
                <span>
                  <span className="block font-display text-xl font-bold text-slate-900">
                    {cartao.titulo}
                    {secao === "No dia do evento" && indice === 0 && (
                      <span className="chip ml-2 border-neon/40 bg-neon-soft align-middle text-neon">
                        Comece aqui
                      </span>
                    )}
                  </span>
                  <span className="block text-sm text-slate-500">{cartao.descricao}</span>
                  {cartao.selo && (
                    <span className="chip mt-2 border-amber-500/40 bg-amber-50 text-amber-700">
                      {cartao.selo}
                    </span>
                  )}
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}

      <section className="mb-8">
        <h2 className="eyebrow mb-3">
          Arquivos
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={baixarBackup}
            disabled={baixando !== null}
            className="card group flex min-h-24 items-start gap-4 p-5 text-left hover:border-neon/60 hover:shadow-glow disabled:opacity-50"
          >
            <span
              aria-hidden="true"
              className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-slate-100 text-3xl ring-1 ring-slate-200 group-hover:ring-neon/40"
            >
              💾
            </span>
            <span>
              <span className="block font-display text-xl font-bold text-slate-900">
                {baixando === "backup" ? "Gerando backup..." : "Baixar backup"}
              </span>
              <span className="block text-sm text-slate-500">
                Cópia completa de tudo (equipes, notas, usuários). Baixe no fim de cada dia.
              </span>
            </span>
          </button>
          <button
            type="button"
            onClick={baixarRelatorio}
            disabled={baixando !== null}
            className="card group flex min-h-24 items-start gap-4 p-5 text-left hover:border-neon/60 hover:shadow-glow disabled:opacity-50"
          >
            <span
              aria-hidden="true"
              className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-slate-100 text-3xl ring-1 ring-slate-200 group-hover:ring-neon/40"
            >
              📄
            </span>
            <span>
              <span className="block font-display text-xl font-bold text-slate-900">
                {baixando === "relatorio" ? "Gerando relatório..." : "Relatório geral (PDF)"}
              </span>
              <span className="block text-sm text-slate-500">
                Classificação e todas as notas de cada modalidade, pra conferência e recurso.
              </span>
            </span>
          </button>
        </div>
        {aviso && <Aviso tipo="sucesso" className="mt-3">{aviso}</Aviso>}
        {erro && <Aviso tipo="erro" className="mt-3">{erro}</Aviso>}
      </section>
    </main>
  );
}
