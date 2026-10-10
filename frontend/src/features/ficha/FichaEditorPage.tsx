import {
  closestCenter,
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { reordenarPorArrasto } from "../../lib/reordenar";

const TIPOS_COM_PONTOS = ["CONTADOR", "BOOLEANO"];

interface CriterioItem {
  id: string;
  grupo_id: string;
  nome: string;
  descricao: string | null;
  categoria: string;
  tipo: string;
  pontos: number | null;
  valores_permitidos: number[] | null;
  max_ocorrencias: number | null;
  modificador_tipo: string | null;
  modificador_valor: number | null;
  ordem: number;
  ativo: boolean;
}

interface GrupoItem {
  id: string;
  ficha_id: string;
  nome: string;
  ordem: number;
  criterios: CriterioItem[];
}

interface FichaCompleta {
  id: string;
  modalidade_id: string;
  nivel: number | null;
  versao: number;
  status: string;
  publicada_em: string | null;
  grupos: GrupoItem[];
}

function CriterioForm({
  valorInicial,
  proximaOrdem,
  onSalvar,
  onCancelar,
}: {
  valorInicial?: CriterioItem;
  proximaOrdem: number;
  onSalvar: (dados: Record<string, unknown>) => void;
  onCancelar: () => void;
}) {
  const [nome, setNome] = useState(valorInicial?.nome ?? "");
  const [categoria, setCategoria] = useState(valorInicial?.categoria ?? "PONTUACAO");
  const [tipo, setTipo] = useState(valorInicial?.tipo ?? "CONTADOR");
  const [pontos, setPontos] = useState(valorInicial?.pontos?.toString() ?? "");
  const [valoresPermitidos, setValoresPermitidos] = useState(
    valorInicial?.valores_permitidos?.join(",") ?? "",
  );
  const [maxOcorrencias, setMaxOcorrencias] = useState(
    valorInicial?.max_ocorrencias?.toString() ?? "",
  );
  const [modificadorTipo, setModificadorTipo] = useState(
    valorInicial?.modificador_tipo ?? "PERCENTUAL",
  );
  const [modificadorValor, setModificadorValor] = useState(
    valorInicial?.modificador_valor?.toString() ?? "",
  );

  function submeter(evento: FormEvent) {
    evento.preventDefault();
    const dados: Record<string, unknown> = {
      nome,
      categoria,
      tipo,
      ordem: valorInicial?.ordem ?? proximaOrdem,
      ativo: true,
    };

    if (TIPOS_COM_PONTOS.includes(tipo)) {
      dados.pontos = Number(pontos);
      if (maxOcorrencias) dados.max_ocorrencias = Number(maxOcorrencias);
    }
    if (tipo === "ESCALA") {
      dados.valores_permitidos = valoresPermitidos
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean)
        .map(Number);
    }
    if (tipo === "MODIFICADOR") {
      dados.modificador_tipo = modificadorTipo;
      if (modificadorTipo === "PERCENTUAL") {
        dados.modificador_valor = Number(modificadorValor);
      }
    }

    onSalvar(dados);
  }

  return (
    <form
      onSubmit={submeter}
      className="space-y-2 rounded border border-slate-300 bg-slate-50 p-3"
    >
      <div>
        <label className="block text-xs text-slate-600" htmlFor="nome-criterio">
          Nome do criterio
        </label>
        <input
          id="nome-criterio"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          className="w-full rounded border border-slate-300 px-2 py-1"
        />
      </div>

      <div>
        <label className="block text-xs text-slate-600" htmlFor="categoria-criterio">
          Tipo de criterio
        </label>
        <select
          id="categoria-criterio"
          value={categoria}
          onChange={(e) => {
            const novaCategoria = e.target.value;
            setCategoria(novaCategoria);
            // ZERA_TOTAL so existe do lado Penalidade; se o usuario voltar
            // para Pontuacao com ZERA_TOTAL selecionado, isso deixaria de
            // ser valido.
            if (novaCategoria === "PONTUACAO" && modificadorTipo === "ZERA_TOTAL") {
              setModificadorTipo("PERCENTUAL");
            }
          }}
          className="w-full rounded border border-slate-300 px-2 py-1"
        >
          <option value="PONTUACAO">Pontuacao</option>
          <option value="PENALIDADE">Penalidade</option>
        </select>
      </div>

      <div>
        <label className="block text-xs text-slate-600" htmlFor="formato-criterio">
          Formato do criterio
        </label>
        <select
          id="formato-criterio"
          value={tipo}
          onChange={(e) => setTipo(e.target.value)}
          className="w-full rounded border border-slate-300 px-2 py-1"
        >
          <option value="CONTADOR">Contador</option>
          <option value="BOOLEANO">Booleano</option>
          <option value="ESCALA">Escala</option>
          <option value="MODIFICADOR">Modificador</option>
        </select>
      </div>

      {TIPOS_COM_PONTOS.includes(tipo) && (
        <>
          <div>
            <label className="block text-xs text-slate-600" htmlFor="pontos-criterio">
              Pontos
            </label>
            <input
              id="pontos-criterio"
              type="number"
              value={pontos}
              onChange={(e) => setPontos(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1"
            />
          </div>
          <div>
            <label
              className="block text-xs text-slate-600"
              htmlFor="max-ocorrencias-criterio"
            >
              Max ocorrencias (opcional)
            </label>
            <input
              id="max-ocorrencias-criterio"
              type="number"
              value={maxOcorrencias}
              onChange={(e) => setMaxOcorrencias(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1"
            />
          </div>
        </>
      )}

      {tipo === "ESCALA" && (
        <div>
          <label
            className="block text-xs text-slate-600"
            htmlFor="valores-permitidos-criterio"
          >
            Valores permitidos (separados por virgula)
          </label>
          <input
            id="valores-permitidos-criterio"
            value={valoresPermitidos}
            onChange={(e) => setValoresPermitidos(e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1"
          />
        </div>
      )}

      {tipo === "MODIFICADOR" && (
        <>
          <div>
            <label
              className="block text-xs text-slate-600"
              htmlFor="modificador-tipo-criterio"
            >
              Tipo de modificador
            </label>
            <select
              id="modificador-tipo-criterio"
              value={modificadorTipo}
              onChange={(e) => setModificadorTipo(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1"
            >
              <option value="PERCENTUAL">Percentual</option>
              {categoria === "PENALIDADE" && <option value="ZERA_TOTAL">Zera total</option>}
            </select>
          </div>
          {modificadorTipo === "PERCENTUAL" && (
            <div>
              <label
                className="block text-xs text-slate-600"
                htmlFor="modificador-valor-criterio"
              >
                Valor do modificador (%)
              </label>
              <input
                id="modificador-valor-criterio"
                type="number"
                value={modificadorValor}
                onChange={(e) => setModificadorValor(e.target.value)}
                className="w-full rounded border border-slate-300 px-2 py-1"
              />
            </div>
          )}
        </>
      )}

      <div className="flex gap-2">
        <button type="submit" className="rounded bg-slate-800 px-3 py-1 text-sm text-white">
          Salvar criterio
        </button>
        <button
          type="button"
          onClick={onCancelar}
          className="rounded border border-slate-300 px-3 py-1 text-sm text-slate-700"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}

function GrupoCard({
  grupo,
  onDeletarGrupo,
  onAdicionarCriterio,
  onAtualizarCriterio,
  onDeletarCriterio,
}: {
  grupo: GrupoItem;
  onDeletarGrupo: (grupoId: string) => void;
  onAdicionarCriterio: (grupoId: string, dados: Record<string, unknown>) => void;
  onAtualizarCriterio: (criterioId: string, dados: Record<string, unknown>) => void;
  onDeletarCriterio: (criterioId: string) => void;
}) {
  const [criandoCriterio, setCriandoCriterio] = useState(false);
  const [criterioEditandoId, setCriterioEditandoId] = useState<string | null>(null);
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: grupo.id,
  });

  const style = { transform: CSS.Transform.toString(transform), transition };

  return (
    <div ref={setNodeRef} style={style} className="rounded border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          {...attributes}
          {...listeners}
          aria-label={`Arrastar ${grupo.nome}`}
          className="cursor-grab px-1 text-slate-400"
        >
          ⠿
        </button>
        <h3 className="flex-1 px-2 font-medium text-slate-800">{grupo.nome}</h3>
        <button
          type="button"
          onClick={() => onDeletarGrupo(grupo.id)}
          className="text-sm text-red-700 underline"
        >
          Remover grupo
        </button>
      </div>

      <ul className="mb-3 space-y-1">
        {grupo.criterios.map((criterio) =>
          criterioEditandoId === criterio.id ? (
            <li key={criterio.id}>
              <CriterioForm
                valorInicial={criterio}
                proximaOrdem={criterio.ordem}
                onSalvar={(dados) => {
                  onAtualizarCriterio(criterio.id, dados);
                  setCriterioEditandoId(null);
                }}
                onCancelar={() => setCriterioEditandoId(null)}
              />
            </li>
          ) : (
            <li
              key={criterio.id}
              className="flex items-center justify-between rounded bg-slate-50 px-2 py-1"
            >
              <span className="text-sm text-slate-800">
                {criterio.nome}{" "}
                <span className="text-xs text-slate-500">({criterio.tipo})</span>{" "}
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    criterio.categoria === "PENALIDADE"
                      ? "bg-red-100 text-red-800"
                      : "bg-green-100 text-green-800"
                  }`}
                >
                  {criterio.categoria === "PENALIDADE" ? "Penalidade" : "Pontuacao"}
                </span>
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setCriterioEditandoId(criterio.id)}
                  className="text-xs font-medium text-slate-700 underline"
                >
                  Editar criterio
                </button>
                <button
                  type="button"
                  onClick={() => onDeletarCriterio(criterio.id)}
                  className="text-xs font-medium text-red-700 underline"
                >
                  Remover
                </button>
              </div>
            </li>
          ),
        )}
      </ul>

      {criandoCriterio ? (
        <CriterioForm
          proximaOrdem={grupo.criterios.length + 1}
          onSalvar={(dados) => {
            onAdicionarCriterio(grupo.id, dados);
            setCriandoCriterio(false);
          }}
          onCancelar={() => setCriandoCriterio(false)}
        />
      ) : (
        <button
          type="button"
          onClick={() => setCriandoCriterio(true)}
          className="text-sm font-medium text-slate-700 underline"
        >
          + Adicionar criterio
        </button>
      )}
    </div>
  );
}

export function FichaEditorPage() {
  const { eventoId, modalidadeId, fichaId } = useParams<{
    eventoId: string;
    modalidadeId: string;
    fichaId: string;
  }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [nomeNovoGrupo, setNomeNovoGrupo] = useState("");

  const { data: ficha } = useQuery({
    queryKey: ["ficha", fichaId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/fichas/{ficha_id}", {
        params: { path: { ficha_id: fichaId! } },
      });
      return data as FichaCompleta | undefined;
    },
    enabled: !!fichaId,
  });

  const sensors = useSensors(useSensor(PointerSensor));

  function invalidarFicha() {
    return queryClient.invalidateQueries({ queryKey: ["ficha", fichaId] });
  }

  async function sincronizarAposCriterio() {
    if (!ficha) return;
    const query: Record<string, unknown> = { modalidade_id: ficha.modalidade_id, size: 10 };
    if (ficha.nivel !== null) query.nivel = ficha.nivel;

    const { data } = await api.GET("/api/v1/fichas", { params: { query } });
    const ativa = data?.itens?.find((f) => f.status !== "SUBSTITUIDA");

    if (ativa && ativa.id !== fichaId) {
      navigate(`/eventos/${eventoId}/modalidades/${modalidadeId}/fichas/${ativa.id}/editar`, {
        replace: true,
      });
    } else {
      await invalidarFicha();
    }
  }

  async function adicionarGrupo(evento: FormEvent) {
    evento.preventDefault();
    if (!nomeNovoGrupo.trim() || !ficha) return;

    const { data } = await api.POST("/api/v1/fichas/{ficha_id}/grupos", {
      params: { path: { ficha_id: fichaId! } },
      body: { nome: nomeNovoGrupo, ordem: ficha.grupos.length + 1 },
    });

    if (data) {
      setNomeNovoGrupo("");
      await invalidarFicha();
    }
  }

  async function atualizarGrupo(grupoId: string, dados: { nome?: string; ordem?: number }) {
    const { data } = await api.PATCH("/api/v1/grupos/{grupo_id}", {
      params: { path: { grupo_id: grupoId } },
      body: dados,
    });
    if (data) await invalidarFicha();
  }

  async function deletarGrupo(grupoId: string) {
    if (!window.confirm("Remover este grupo e todos os seus criterios?")) return;
    await api.DELETE("/api/v1/grupos/{grupo_id}", { params: { path: { grupo_id: grupoId } } });
    await invalidarFicha();
  }

  async function adicionarCriterio(grupoId: string, dados: Record<string, unknown>) {
    await api.POST("/api/v1/grupos/{grupo_id}/criterios", {
      params: { path: { grupo_id: grupoId } },
      body: dados as never,
    });
    await sincronizarAposCriterio();
  }

  async function atualizarCriterio(criterioId: string, dados: Record<string, unknown>) {
    await api.PATCH("/api/v1/criterios/{criterio_id}", {
      params: { path: { criterio_id: criterioId } },
      body: dados as never,
    });
    await sincronizarAposCriterio();
  }

  async function deletarCriterio(criterioId: string) {
    if (!window.confirm("Remover este criterio?")) return;
    await api.DELETE("/api/v1/criterios/{criterio_id}", {
      params: { path: { criterio_id: criterioId } },
    });
    await sincronizarAposCriterio();
  }

  async function publicar() {
    await api.POST("/api/v1/fichas/{ficha_id}/publicar", {
      params: { path: { ficha_id: fichaId! } },
    });
    await invalidarFicha();
  }

  function handleDragEnd(event: DragEndEvent) {
    if (!ficha) return;
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const reordenados = reordenarPorArrasto(ficha.grupos, String(active.id), String(over.id));
    for (const grupo of reordenados) {
      const original = ficha.grupos.find((g) => g.id === grupo.id);
      if (original && original.ordem !== grupo.ordem) {
        void atualizarGrupo(grupo.id, { ordem: grupo.ordem });
      }
    }
  }

  if (!ficha) {
    return <main className="p-8 text-slate-500">Carregando...</main>;
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-800">Editor de ficha</h1>
        <div className="flex items-center gap-3">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
            v{ficha.versao} · {ficha.status}
          </span>
          <Link
            to={`/eventos/${eventoId}/modalidades/${modalidadeId}/fichas/${fichaId}/preview`}
            className="text-sm font-medium text-slate-700 underline"
          >
            Preview mobile
          </Link>
        </div>
      </div>

      {ficha.status === "PUBLICADA" && (
        <div className="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p className="font-semibold">Esta ficha está publicada (em uso pelos juízes).</p>
          <p>
            Qualquer edição cria uma nova versão automaticamente, e as próximas notas já usam a
            versão nova. As notas já lançadas não mudam: continuam valendo pela versão antiga.
          </p>
        </div>
      )}

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext
          items={ficha.grupos.map((g) => g.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-4">
            {ficha.grupos.map((grupo) => (
              <GrupoCard
                key={grupo.id}
                grupo={grupo}
                onDeletarGrupo={deletarGrupo}
                onAdicionarCriterio={adicionarCriterio}
                onAtualizarCriterio={atualizarCriterio}
                onDeletarCriterio={deletarCriterio}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      <form onSubmit={adicionarGrupo} className="mt-4 flex items-end gap-2">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nome-novo-grupo">
            Nome do grupo
          </label>
          <input
            id="nome-novo-grupo"
            value={nomeNovoGrupo}
            onChange={(e) => setNomeNovoGrupo(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2"
          />
        </div>
        <button
          type="submit"
          className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white"
        >
          Adicionar grupo
        </button>
      </form>

      {ficha.status === "RASCUNHO" && (
        <button
          type="button"
          onClick={publicar}
          className="mt-6 rounded bg-emerald-700 px-4 py-2 font-medium text-white"
        >
          Publicar ficha
        </button>
      )}
    </main>
  );
}
