import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, extrairErro } from "../../api/client";
import type { components } from "../../api/types";
import { Aviso } from "../../components/Aviso";

type Pedido = components["schemas"]["SolicitacaoAcessoOut"];
type Decisao = "aprovar" | "recusar";
type PapelAprovado = "ARBITRO" | "COORDENADOR";

const NOME_PAPEL: Record<PapelAprovado, string> = { ARBITRO: "juiz", COORDENADOR: "coordenador" };

const FORMATO_DATA = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "America/Fortaleza",
});

function CardPedido({
  pedido,
  onDecidido,
}: {
  pedido: Pedido;
  onDecidido: (mensagem: string) => Promise<void>;
}) {
  const [confirmando, setConfirmando] = useState<Decisao | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar(chamada: Promise<{ error?: unknown }>, mensagem: string) {
    setEnviando(true);
    setErro(null);
    const { error } = await chamada;
    setEnviando(false);
    setConfirmando(null);
    if (error) {
      setErro(extrairErro(error).mensagem);
      return;
    }
    await onDecidido(mensagem);
  }

  const params = { params: { path: { solicitacao_id: pedido.id } } };

  function aprovar(papel: PapelAprovado) {
    return enviar(
      api.POST("/api/v1/solicitacoes-acesso/{solicitacao_id}/aprovar", {
        ...params,
        body: { papel },
      }),
      `Conta de ${NOME_PAPEL[papel]} de ${pedido.nome} criada. Já pode entrar com o e-mail e a senha que escolheu.`,
    );
  }

  function recusar() {
    return enviar(
      api.POST("/api/v1/solicitacoes-acesso/{solicitacao_id}/recusar", params),
      `Pedido de ${pedido.nome} recusado.`,
    );
  }

  return (
    <li className="card p-4">
      <p className="font-semibold text-slate-900">{pedido.nome}</p>
      <p className="break-all text-sm text-slate-600">{pedido.email}</p>
      <p className="mt-1 text-xs text-slate-500">
        Pediu em {FORMATO_DATA.format(new Date(pedido.criado_em))}
      </p>

      {erro && (
        <Aviso tipo="erro" className="mt-3">
          {erro}
        </Aviso>
      )}

      {confirmando === "aprovar" ? (
        <div className="mt-3">
          <p className="mb-2 text-sm text-slate-700">Criar conta pra {pedido.nome} como:</p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              disabled={enviando}
              onClick={() => aprovar("ARBITRO")}
              className="btn-success min-h-12"
            >
              Criar como juiz
            </button>
            <button
              type="button"
              disabled={enviando}
              onClick={() => aprovar("COORDENADOR")}
              className="btn-secondary min-h-12"
            >
              Criar como coordenador
            </button>
            <p className="text-xs text-slate-500">
              Coordenador pode mexer em tudo: notas, equipes, contas e configurações.
            </p>
            <button
              type="button"
              disabled={enviando}
              onClick={() => setConfirmando(null)}
              className="btn-secondary min-h-12"
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : confirmando === "recusar" ? (
        <div className="mt-3">
          <p className="mb-2 text-sm text-slate-700">Recusar o pedido de {pedido.nome}?</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={enviando}
              onClick={recusar}
              className="btn-danger min-h-12 flex-1"
            >
              Sim, recusar
            </button>
            <button
              type="button"
              disabled={enviando}
              onClick={() => setConfirmando(null)}
              className="btn-secondary min-h-12 flex-1"
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setConfirmando("aprovar")}
            className="btn-success min-h-12 flex-1"
          >
            Aprovar
          </button>
          <button
            type="button"
            onClick={() => setConfirmando("recusar")}
            className="btn-secondary min-h-12 flex-1"
          >
            Recusar
          </button>
        </div>
      )}
    </li>
  );
}

// Pedidos de conta feitos pelos proprios juizes (tela /pedir-acesso). A conta
// so nasce quando o coordenador aprova aqui.
export function PedidosAcesso() {
  const queryClient = useQueryClient();
  const [aviso, setAviso] = useState<string | null>(null);

  const { data: pedidos, isLoading } = useQuery({
    queryKey: ["solicitacoes-acesso"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/solicitacoes-acesso");
      return Array.isArray(data) ? data : [];
    },
  });

  async function aoDecidir(mensagem: string) {
    setAviso(mensagem);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["solicitacoes-acesso"] }),
      queryClient.invalidateQueries({ queryKey: ["usuarios"] }),
    ]);
  }

  const total = pedidos?.length ?? 0;

  return (
    <section className="mb-10">
      <h2 className="eyebrow mb-1">Pedidos de acesso ({total})</h2>
      <p className="mb-3 text-sm text-slate-500">
        Antes de aprovar, confira no grupo dos juízes se a pessoa é mesmo juiz.
      </p>

      {aviso && (
        <Aviso tipo="sucesso" className="mb-3">
          {aviso}
        </Aviso>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Carregando...</p>
      ) : total === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
          Nenhum pedido esperando. O juiz novo pede acesso pela tela de login, em "Sou juiz e ainda
          não tenho conta".
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {pedidos!.map((pedido) => (
            <CardPedido key={pedido.id} pedido={pedido} onDecidido={aoDecidir} />
          ))}
        </ul>
      )}
    </section>
  );
}
