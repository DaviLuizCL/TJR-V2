import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";

interface ItemAuditoria {
  criterio_snapshot: {
    nome: string;
    categoria: string;
    tipo?: string;
    modificador_tipo?: string | null;
    modificador_valor?: number | null;
    aplicado?: boolean;
  };
  pontos: number;
}

interface LancamentoAuditoria {
  id: string;
  modalidade_nome: string;
  nivel: number | null;
  equipe_nome: string;
  rodada_numero: number;
  tentativa: number;
  responsavel_nome: string;
  horario_submissao: string;
  status: string;
  total: number;
  itens: ItemAuditoria[];
}

function formatarHorario(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Fortaleza",
    dateStyle: "short",
    timeStyle: "short",
  });
}

function ehModificador(i: ItemAuditoria): boolean {
  return i.criterio_snapshot.tipo === "MODIFICADOR";
}

function efeitoModificador(i: ItemAuditoria): string {
  if (!i.criterio_snapshot.aplicado) return "Não aplicado";
  if (i.criterio_snapshot.modificador_tipo === "ZERA_TOTAL") return "Zera o total";
  const sinal = i.criterio_snapshot.categoria === "PENALIDADE" ? "-" : "+";
  return `${sinal}${i.criterio_snapshot.modificador_valor}%`;
}

function CardSubmissao({ item }: { item: LancamentoAuditoria }) {
  const pontuados = item.itens.filter(
    (i) => i.criterio_snapshot.categoria === "PONTUACAO" && i.pontos !== 0 && !ehModificador(i),
  );
  const zerados = item.itens.filter((i) => i.pontos === 0 && !ehModificador(i));
  const penalidades = item.itens.filter(
    (i) => i.criterio_snapshot.categoria === "PENALIDADE" && i.pontos !== 0 && !ehModificador(i),
  );
  const modificadores = item.itens.filter(ehModificador);

  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-800">
            {item.modalidade_nome}
            {item.nivel !== null ? ` · Nivel ${item.nivel}` : ""}
          </p>
          <p className="text-xs text-slate-500">
            {item.equipe_nome} · Rodada {item.rodada_numero} · Tentativa {item.tentativa} · ID{" "}
            {item.id}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-slate-900">{item.total}</p>
          <p className="text-xs text-slate-500">{formatarHorario(item.horario_submissao)}</p>
        </div>
      </div>

      <p className="mt-2 text-sm text-slate-600">
        Lancado por <span className="font-medium">{item.responsavel_nome}</span> · {item.status}
      </p>

      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Pontuados
          </p>
          <ul className="text-sm text-slate-700">
            {pontuados.length === 0 && <li className="text-slate-400">Nenhum</li>}
            {pontuados.map((i, idx) => (
              <li key={idx}>
                {i.criterio_snapshot.nome}: {i.pontos}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Não pontuados
          </p>
          <ul className="text-sm text-slate-700">
            {zerados.length === 0 && <li className="text-slate-400">Nenhum</li>}
            {zerados.map((i, idx) => (
              <li key={idx}>{i.criterio_snapshot.nome}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Penalidades
          </p>
          <ul className="text-sm text-slate-700">
            {penalidades.length === 0 && <li className="text-slate-400">Nenhuma</li>}
            {penalidades.map((i, idx) => (
              <li key={idx}>
                {i.criterio_snapshot.nome}: {i.pontos}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {modificadores.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Modificadores
          </p>
          <ul className="text-sm text-slate-700">
            {modificadores.map((i, idx) => (
              <li key={idx} className="flex items-center justify-between">
                <span>{i.criterio_snapshot.nome}</span>
                <span
                  className={
                    i.criterio_snapshot.aplicado ? "font-medium text-slate-800" : "text-slate-400"
                  }
                >
                  {efeitoModificador(i)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

export function ListaSubmissoes({
  eventoId,
  modalidadeId,
  rodadaId,
  equipeId,
  mensagemVazia = "Nenhuma submissao ainda.",
}: {
  eventoId?: string;
  modalidadeId?: string;
  rodadaId?: string;
  equipeId?: string;
  mensagemVazia?: string;
}) {
  const { data } = useQuery({
    queryKey: ["submissoes-auditoria", eventoId, modalidadeId, rodadaId, equipeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/lancamentos/auditoria", {
        params: {
          query: {
            ...(eventoId ? { evento_id: eventoId } : {}),
            ...(modalidadeId ? { modalidade_id: modalidadeId } : {}),
            ...(rodadaId ? { rodada_id: rodadaId } : {}),
            ...(equipeId ? { equipe_id: equipeId } : {}),
            size: 100,
          },
        },
      });
      return (data?.itens ?? []) as unknown as LancamentoAuditoria[];
    },
  });

  if (!data) return <p className="text-slate-500">Carregando...</p>;
  if (data.length === 0) return <p className="text-slate-500">{mensagemVazia}</p>;

  return (
    <ul className="space-y-3">
      {data.map((item) => (
        <CardSubmissao key={item.id} item={item} />
      ))}
    </ul>
  );
}
