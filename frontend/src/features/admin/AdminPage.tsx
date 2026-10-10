import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, extrairErro } from "../../api/client";
import { useEventoStore } from "../../lib/evento-store";

interface Cartao {
  icone: string;
  titulo: string;
  descricao: string;
  destino: string;
}

function cartoes(eventoId: string): { secao: string; itens: Cartao[] }[] {
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
      ],
    },
    {
      secao: "Preparação",
      itens: [
        {
          icone: "🔑",
          titulo: "Juízes e senhas",
          descricao: "Cadastrar juiz, trocar senha esquecida, desativar conta.",
          destino: "/usuarios",
        },
        {
          icone: "📥",
          titulo: "Importar equipes",
          descricao: "Sobe a planilha de inscrições e cadastra as equipes de uma vez.",
          destino: `${evento}/admin/importar`,
        },
        {
          icone: "📋",
          titulo: "Fichas de pontuação",
          descricao: "Ver ou alterar os critérios de pontuação de cada modalidade.",
          destino: `${evento}/fichas`,
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
    <main className="mx-auto max-w-4xl p-4 sm:p-8">
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">Administração</h1>
      <p className="mb-6 text-sm text-slate-500">
        Tudo que o coordenador precisa pra tocar o evento. Em dúvida, comece pelo checklist do
        dia.
      </p>

      {cartoes(eventoId!).map(({ secao, itens }) => (
        <section key={secao} className="mb-8">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
            {secao}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {itens.map((cartao) => (
              <Link
                key={cartao.titulo}
                to={cartao.destino}
                className="flex min-h-24 items-start gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-400"
              >
                <span aria-hidden="true" className="text-3xl">
                  {cartao.icone}
                </span>
                <span>
                  <span className="block text-lg font-semibold text-slate-800">
                    {cartao.titulo}
                  </span>
                  <span className="block text-sm text-slate-500">{cartao.descricao}</span>
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Arquivos
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={baixarBackup}
            disabled={baixando !== null}
            className="flex min-h-24 items-start gap-4 rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-slate-400 disabled:opacity-50"
          >
            <span aria-hidden="true" className="text-3xl">
              💾
            </span>
            <span>
              <span className="block text-lg font-semibold text-slate-800">
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
            className="flex min-h-24 items-start gap-4 rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-slate-400 disabled:opacity-50"
          >
            <span aria-hidden="true" className="text-3xl">
              📄
            </span>
            <span>
              <span className="block text-lg font-semibold text-slate-800">
                {baixando === "relatorio" ? "Gerando relatório..." : "Relatório geral (PDF)"}
              </span>
              <span className="block text-sm text-slate-500">
                Classificação e todas as notas de cada modalidade, pra conferência e recurso.
              </span>
            </span>
          </button>
        </div>
        {aviso && <p className="mt-3 font-medium text-emerald-700">{aviso}</p>}
        {erro && <p className="mt-3 font-medium text-red-600">{erro}</p>}
      </section>
    </main>
  );
}
