import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, extrairErro } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { EmptyState } from "../../components/EmptyState";
import { avisar } from "../../lib/avisos";
import { useAuthStore } from "../../lib/auth-store";
import {
  TIPOS_REGRA,
  urlRegra,
  type ModalidadeComRegras,
  type TipoRegra,
} from "../../lib/regras";

interface LinhaRegraProps {
  modalidade: ModalidadeComRegras;
  tipo: TipoRegra;
  rotulo: string;
  podeEditar: boolean;
  aoMudar: () => Promise<unknown>;
}

function LinhaRegra({ modalidade, tipo, rotulo, podeEditar, aoMudar }: LinhaRegraProps) {
  const regra = modalidade.regras.find((r) => r.tipo === tipo);
  const [enviando, setEnviando] = useState(false);
  const [confirmandoRemocao, setConfirmandoRemocao] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const caminho = { modalidade_id: modalidade.id, tipo };

  async function enviar(arquivo: File | undefined) {
    if (!arquivo) return;
    const formulario = new FormData();
    formulario.append("arquivo", arquivo);
    setEnviando(true);
    setErro(null);
    const { error } = await api.PUT("/api/v1/modalidades/{modalidade_id}/regras/{tipo}", {
      params: { path: caminho },
      body: formulario as never,
    });
    setEnviando(false);
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    avisar("sucesso", `${rotulo} de ${modalidade.nome} enviado.`);
    await aoMudar();
  }

  async function remover() {
    setConfirmandoRemocao(false);
    const { error } = await api.DELETE("/api/v1/modalidades/{modalidade_id}/regras/{tipo}", {
      params: { path: caminho },
    });
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    avisar("sucesso", `${rotulo} de ${modalidade.nome} removido.`);
    await aoMudar();
  }

  return (
    <li className="rounded-lg border border-slate-200 px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold text-slate-900">{rotulo}</p>
          {regra ? (
            <p className="break-all text-sm text-emerald-700">{regra.nome_arquivo}</p>
          ) : (
            <p className="text-sm text-slate-500">Nenhum PDF enviado</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {regra && (
            <a
              href={urlRegra(modalidade.id, tipo)}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary min-h-12"
            >
              Ver
            </a>
          )}
          {podeEditar && (
            <label className={`btn-primary min-h-12 cursor-pointer ${enviando ? "opacity-60" : ""}`}>
              {enviando ? "Enviando..." : regra ? "Trocar PDF" : "Enviar PDF"}
              <input
                type="file"
                accept="application/pdf,.pdf"
                aria-label={`Enviar ${rotulo} de ${modalidade.nome}`}
                disabled={enviando}
                className="sr-only"
                onChange={(e) => {
                  void enviar(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </label>
          )}
          {podeEditar && regra && !confirmandoRemocao && (
            <button
              type="button"
              onClick={() => setConfirmandoRemocao(true)}
              className="btn-secondary min-h-12"
            >
              Remover
            </button>
          )}
        </div>
      </div>
      {confirmandoRemocao && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-sm text-slate-600">Tirar esse PDF do site?</span>
          <button type="button" onClick={() => void remover()} className="btn-danger min-h-12">
            Sim, remover
          </button>
          <button
            type="button"
            onClick={() => setConfirmandoRemocao(false)}
            className="btn-secondary min-h-12"
          >
            Cancelar
          </button>
        </div>
      )}
      {erro && <p className="mt-2 text-sm text-red-700">{erro}</p>}
    </li>
  );
}

// Aba do Painel: o coordenador envia o manual completo e o caderninho do aluno
// de cada modalidade. O publico le em /regras, na tela inicial.
export function RegrasModalidadeTab() {
  const ehCoordenador = useAuthStore((state) => state.usuario?.papel) === "COORDENADOR";
  const queryClient = useQueryClient();

  const { data: modalidades, isLoading } = useQuery({
    queryKey: ["publico-regras"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/publico/regras");
      return (data ?? []) as ModalidadeComRegras[];
    },
  });

  const recarregar = () => queryClient.invalidateQueries({ queryKey: ["publico-regras"] });

  if (isLoading) return <p className="text-slate-500">Carregando...</p>;
  if (!modalidades || modalidades.length === 0) {
    return <EmptyState titulo="Nenhuma modalidade cadastrada ainda." />;
  }

  return (
    <div className="space-y-4">
      <Aviso tipo="info">
        Os PDFs aparecem pra qualquer pessoa no botão "Regras" da tela inicial. Enviar de novo
        troca o arquivo.
      </Aviso>
      {modalidades.map((modalidade) => {
        const idTitulo = `regras-${modalidade.id}`;
        return (
          <section key={modalidade.id} aria-labelledby={idTitulo} className="card p-4">
            <h2 id={idTitulo} className="mb-3 text-xl font-bold">
              {modalidade.nome}
            </h2>
            <ul className="space-y-2">
              {TIPOS_REGRA.map(({ tipo, rotulo }) => (
                <LinhaRegra
                  key={tipo}
                  modalidade={modalidade}
                  tipo={tipo}
                  rotulo={rotulo}
                  podeEditar={ehCoordenador}
                  aoMudar={recarregar}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
