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
  partida_id: string | null;
}

interface GrupoCombate {
  chave: string;
  modalidade_nome: string;
  nivel: number | null;
  rodada_numero: number;
  tentativa: number;
  lados: LancamentoAuditoria[];
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

function agruparPorCombate(itens: LancamentoAuditoria[]): (LancamentoAuditoria | GrupoCombate)[] {
  const grupoPorChave = new Map<string, GrupoCombate>();
  const resultado: (LancamentoAuditoria | GrupoCombate)[] = [];

  for (const item of itens) {
    if (!item.partida_id) {
      resultado.push(item);
      continue;
    }

    const chave = `${item.partida_id}-${item.tentativa}`;
    let grupo = grupoPorChave.get(chave);
    if (!grupo) {
      grupo = {
        chave,
        modalidade_nome: item.modalidade_nome,
        nivel: item.nivel,
        rodada_numero: item.rodada_numero,
        tentativa: item.tentativa,
        lados: [],
      };
      grupoPorChave.set(chave, grupo);
      resultado.push(grupo);
    }
    grupo.lados.push(item);
  }

  return resultado;
}

function ehGrupoCombate(item: LancamentoAuditoria | GrupoCombate): item is GrupoCombate {
  return "lados" in item;
}

function LadoCombate({
  lancamento,
  vencedor,
  empate,
}: {
  lancamento: LancamentoAuditoria;
  vencedor: boolean;
  empate: boolean;
}) {
  return (
    <div
      className={`rounded border p-3 ${
        vencedor ? "border-green-400 bg-green-50" : "border-slate-200"
      }`}
    >
      <p className="font-medium text-slate-800">{lancamento.equipe_nome}</p>
      <p className="text-2xl font-bold text-slate-900">{lancamento.total}</p>
      {vencedor && <p className="text-xs font-medium text-green-700">Vencedor</p>}
      {empate && <p className="text-xs font-medium text-slate-500">Empate</p>}
    </div>
  );
}

function CardCombate({ grupo }: { grupo: GrupoCombate }) {
  const [ladoA, ladoB] = grupo.lados;
  const decidido = grupo.lados.length === 2;
  const empate = decidido && ladoA.total === ladoB.total;
  const ladoAVenceu = decidido && !empate && ladoA.total > ladoB.total;
  const ladoBVenceu = decidido && !empate && ladoB.total > ladoA.total;

  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <p className="font-semibold text-slate-800">
        {grupo.modalidade_nome}
        {grupo.nivel !== null ? ` · Nivel ${grupo.nivel}` : ""}
      </p>
      <p className="mb-3 text-xs text-slate-500">
        Rodada {grupo.rodada_numero} · Tentativa {grupo.tentativa}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <LadoCombate lancamento={ladoA} vencedor={ladoAVenceu} empate={empate} />
        {ladoB ? (
          <LadoCombate lancamento={ladoB} vencedor={ladoBVenceu} empate={empate} />
        ) : (
          <div className="flex items-center rounded border border-dashed border-slate-300 p-3 text-sm text-slate-400">
            Aguardando a equipe adversária
          </div>
        )}
      </div>
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
      {agruparPorCombate(data).map((item) =>
        ehGrupoCombate(item) ? (
          <CardCombate key={item.chave} grupo={item} />
        ) : (
          <CardSubmissao key={item.id} item={item} />
        ),
      )}
    </ul>
  );
}
