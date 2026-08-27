import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";
import { rotuloNivel } from "../../lib/nivel";

const NIVEIS = [1, 2, 3, 4] as const;

const schema = z.object({
  nome: z.string().trim().min(1, "Informe o nome da equipe"),
  nivel: z.coerce.number().int().min(1).max(4),
  modalidadeIds: z.array(z.string()).default([]),
});

type FormData = z.infer<typeof schema>;

interface EquipeItem {
  id: string;
  nome: string;
  nivel: number;
  ativo: boolean;
}

function EquipeEditForm({
  equipe,
  onSalvar,
  onCancelar,
}: {
  equipe: EquipeItem;
  onSalvar: (dados: { nome: string; nivel: number }) => void;
  onCancelar: () => void;
}) {
  const [nome, setNome] = useState(equipe.nome);
  const [nivel, setNivel] = useState(equipe.nivel);

  return (
    <div className="flex flex-1 items-end gap-2">
      <div>
        <label className="block text-xs text-slate-600" htmlFor={`nome-editar-${equipe.id}`}>
          Nome
        </label>
        <input
          id={`nome-editar-${equipe.id}`}
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1"
        />
      </div>
      <div>
        <label className="block text-xs text-slate-600" htmlFor={`nivel-editar-${equipe.id}`}>
          Nivel
        </label>
        <select
          id={`nivel-editar-${equipe.id}`}
          value={nivel}
          onChange={(e) => setNivel(Number(e.target.value))}
          className="rounded border border-slate-300 px-2 py-1"
        >
          {NIVEIS.map((n) => (
            <option key={n} value={n}>
              {rotuloNivel(n)}
            </option>
          ))}
        </select>
      </div>
      <button
        type="button"
        onClick={() => onSalvar({ nome, nivel })}
        className="rounded bg-slate-800 px-3 py-1 text-sm text-white"
      >
        Salvar
      </button>
      <button
        type="button"
        onClick={onCancelar}
        className="rounded border border-slate-300 px-3 py-1 text-sm text-slate-700"
      >
        Cancelar
      </button>
    </div>
  );
}

interface ModalidadeItem {
  id: string;
  nome: string;
  niveis_aplicaveis: number[];
}

interface InscricaoItem {
  id: string;
  equipe_id: string;
  modalidade_id: string;
}

function EquipeModalidadesPanel({
  equipe,
  modalidades,
  inscricoesDaEquipe,
  onAdicionar,
  onRemover,
}: {
  equipe: EquipeItem;
  modalidades: ModalidadeItem[];
  inscricoesDaEquipe: InscricaoItem[];
  onAdicionar: (modalidadeId: string) => void;
  onRemover: (inscricaoId: string) => void;
}) {
  const [modalidadeSelecionada, setModalidadeSelecionada] = useState("");
  const modalidadePorId = new Map(modalidades.map((m) => [m.id, m]));
  const idsInscritos = new Set(inscricoesDaEquipe.map((i) => i.modalidade_id));
  const elegiveis = modalidades.filter(
    (m) => !idsInscritos.has(m.id) && m.niveis_aplicaveis.includes(equipe.nivel),
  );

  return (
    <div
      aria-label={`Modalidades de ${equipe.nome}`}
      className="mt-3 w-full rounded border border-slate-200 bg-slate-50 p-4"
    >
      <ul className="mb-3 space-y-1">
        {inscricoesDaEquipe.map((inscricao) => (
          <li key={inscricao.id} className="flex items-center justify-between text-sm">
            <span>{modalidadePorId.get(inscricao.modalidade_id)?.nome ?? "?"}</span>
            <button
              type="button"
              onClick={() => onRemover(inscricao.id)}
              className="font-medium text-red-700 underline"
            >
              Remover
            </button>
          </li>
        ))}
        {inscricoesDaEquipe.length === 0 && (
          <p className="text-sm text-slate-500">Nenhuma modalidade ainda.</p>
        )}
      </ul>

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label
            className="mb-1 block text-xs text-slate-600"
            htmlFor={`add-modalidade-${equipe.id}`}
          >
            Adicionar modalidade
          </label>
          <select
            id={`add-modalidade-${equipe.id}`}
            value={modalidadeSelecionada}
            onChange={(e) => setModalidadeSelecionada(e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">Selecione</option>
            {elegiveis.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          disabled={!modalidadeSelecionada}
          onClick={() => {
            onAdicionar(modalidadeSelecionada);
            setModalidadeSelecionada("");
          }}
          className="rounded bg-slate-800 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          Adicionar
        </button>
      </div>
    </div>
  );
}

export function EquipeListPage() {
  const queryClient = useQueryClient();
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [filtroNivel, setFiltroNivel] = useState<string>("");
  const [filtroModalidadeId, setFiltroModalidadeId] = useState<string>("");
  const [buscaNome, setBuscaNome] = useState<string>("");
  const [equipeEditandoId, setEquipeEditandoId] = useState<string | null>(null);
  const ehCoordenador = useAuthStore((state) => state.usuario?.papel) === "COORDENADOR";

  const { data: modalidades } = useQuery({
    queryKey: ["modalidades-filtro-equipe"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades", { params: { query: { size: 200 } } });
      return (data?.itens ?? []) as ModalidadeItem[];
    },
  });

  const { data, isLoading } = useQuery({
    queryKey: ["equipes", filtroNivel, filtroModalidadeId],
    queryFn: async () => {
      const query: Record<string, unknown> = { size: 1000 };
      if (filtroNivel) query.nivel = Number(filtroNivel);
      if (filtroModalidadeId) query.modalidade_id = filtroModalidadeId;
      const { data } = await api.GET("/api/v1/equipes", { params: { query } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  const dataFiltrada = data?.filter((equipe) =>
    equipe.nome.toLowerCase().includes(buscaNome.trim().toLowerCase()),
  );

  const { data: inscricoes } = useQuery({
    queryKey: ["inscricoes", "todas-para-equipes"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/inscricoes", { params: { query: { size: 1000 } } });
      return (data?.itens ?? []) as InscricaoItem[];
    },
  });

  const modalidadeNomePorId = new Map((modalidades ?? []).map((m) => [m.id, m.nome]));
  const modalidadesPorEquipe = new Map<string, string[]>();
  for (const inscricao of inscricoes ?? []) {
    const nome = modalidadeNomePorId.get(inscricao.modalidade_id);
    if (!nome) continue;
    if (!modalidadesPorEquipe.has(inscricao.equipe_id)) {
      modalidadesPorEquipe.set(inscricao.equipe_id, []);
    }
    modalidadesPorEquipe.get(inscricao.equipe_id)!.push(nome);
  }

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { nivel: 1, modalidadeIds: [] },
    shouldUnregister: true,
  });
  const nivelDoFormulario = Number(watch("nivel") ?? 1);
  const modalidadesElegiveisParaCriar = (modalidades ?? []).filter((m) =>
    (m.niveis_aplicaveis ?? []).includes(nivelDoFormulario),
  );

  async function invalidar() {
    await queryClient.invalidateQueries({ queryKey: ["equipes"] });
  }

  async function invalidarInscricoes() {
    await queryClient.invalidateQueries({ queryKey: ["inscricoes"] });
  }

  async function adicionarModalidade(equipeId: string, modalidadeId: string) {
    if (!modalidadeId) return;
    await api.POST("/api/v1/inscricoes", {
      body: { equipe_id: equipeId, modalidade_id: modalidadeId },
    });
    await invalidarInscricoes();
  }

  async function removerModalidade(inscricaoId: string) {
    await api.DELETE("/api/v1/inscricoes/{inscricao_id}", {
      params: { path: { inscricao_id: inscricaoId } },
    });
    await invalidarInscricoes();
  }

  async function onSubmit(dados: FormData) {
    setErroGeral(null);
    const { modalidadeIds, ...equipeDados } = dados;
    // ativo tem default no backend (Pydantic), mas o openapi-typescript gera esse
    // campo como obrigatorio no tipo do payload sempre que ha um valor default.
    const { data, error } = await api.POST("/api/v1/equipes", {
      body: { ...equipeDados, ativo: true },
    });

    if (error) {
      setErroGeral(extrairErro(error).mensagem);
      return;
    }

    for (const modalidadeId of modalidadeIds) {
      await api.POST("/api/v1/inscricoes", {
        body: { equipe_id: data.id, modalidade_id: modalidadeId },
      });
    }

    reset({ nome: "", nivel: 1, modalidadeIds: [] });
    await invalidar();
    if (modalidadeIds.length > 0) {
      await invalidarInscricoes();
    }
  }

  async function alternarAtivo(equipe: EquipeItem) {
    await api.PATCH("/api/v1/equipes/{equipe_id}", {
      params: { path: { equipe_id: equipe.id } },
      body: { ativo: !equipe.ativo },
    });
    await invalidar();
  }

  async function salvarEdicao(equipeId: string, dados: { nome: string; nivel: number }) {
    await api.PATCH("/api/v1/equipes/{equipe_id}", {
      params: { path: { equipe_id: equipeId } },
      body: dados,
    });
    setEquipeEditandoId(null);
    await invalidar();
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Equipes</h1>

      <section className="mb-10">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
            Equipes cadastradas
          </h2>
          <div className="flex items-center gap-4">
            <div>
              <label className="mr-2 text-sm text-slate-600" htmlFor="busca-nome">
                Buscar equipe
              </label>
              <input
                id="busca-nome"
                type="text"
                value={buscaNome}
                onChange={(e) => setBuscaNome(e.target.value)}
                placeholder="Nome da equipe"
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="mr-2 text-sm text-slate-600" htmlFor="filtro-nivel">
                Filtrar por nivel
              </label>
              <select
                id="filtro-nivel"
                value={filtroNivel}
                onChange={(e) => setFiltroNivel(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">Todos</option>
                {NIVEIS.map((n) => (
                  <option key={n} value={n}>
                    {rotuloNivel(n)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mr-2 text-sm text-slate-600" htmlFor="filtro-modalidade">
                Filtrar por modalidade
              </label>
              <select
                id="filtro-modalidade"
                value={filtroModalidadeId}
                onChange={(e) => setFiltroModalidadeId(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">Todas</option>
                {modalidades?.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nome}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {isLoading && <p className="text-slate-500">Carregando...</p>}
        {!isLoading && data?.length === 0 && (
          <p className="text-slate-500">Nenhuma equipe cadastrada ainda.</p>
        )}
        {!isLoading && (data?.length ?? 0) > 0 && dataFiltrada?.length === 0 && (
          <p className="text-slate-500">Nenhuma equipe encontrada para essa busca.</p>
        )}

        <ul className="space-y-2">
          {dataFiltrada?.map((equipe) => (
            <li
              key={equipe.id}
              className="flex flex-col rounded border border-slate-200 bg-white px-4 py-3"
            >
              {ehCoordenador && equipeEditandoId === equipe.id ? (
                <>
                  <EquipeEditForm
                    equipe={equipe}
                    onSalvar={(dados) => salvarEdicao(equipe.id, dados)}
                    onCancelar={() => setEquipeEditandoId(null)}
                  />
                  <EquipeModalidadesPanel
                    equipe={equipe}
                    modalidades={modalidades ?? []}
                    inscricoesDaEquipe={(inscricoes ?? []).filter(
                      (i) => i.equipe_id === equipe.id,
                    )}
                    onAdicionar={(modalidadeId) => adicionarModalidade(equipe.id, modalidadeId)}
                    onRemover={removerModalidade}
                  />
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium text-slate-800">{equipe.nome}</span>
                      <span className="ml-2 text-sm text-slate-500">
                        {rotuloNivel(equipe.nivel)}
                      </span>
                      <p className="mt-1 text-sm text-slate-500">
                        {modalidadesPorEquipe.get(equipe.id)?.length ? (
                          <>Modalidades: {modalidadesPorEquipe.get(equipe.id)!.join(", ")}</>
                        ) : (
                          "Nenhuma modalidade"
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          equipe.ativo
                            ? "bg-green-100 text-green-800"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {equipe.ativo ? "Ativa" : "Inativa"}
                      </span>
                      <Link
                        to={`/equipes/${equipe.id}/submissoes`}
                        className="text-sm font-medium text-slate-700 underline"
                      >
                        Submissões
                      </Link>
                      {ehCoordenador && (
                        <button
                          type="button"
                          onClick={() => setEquipeEditandoId(equipe.id)}
                          className="text-sm font-medium text-slate-700 underline"
                        >
                          Editar
                        </button>
                      )}
                      {ehCoordenador && (
                        <button
                          type="button"
                          onClick={() => alternarAtivo(equipe)}
                          className="text-sm font-medium text-slate-700 underline"
                        >
                          {equipe.ativo ? "Desativar" : "Ativar"}
                        </button>
                      )}
                    </div>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      </section>

      {ehCoordenador && (
      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Criar nova equipe
        </h2>
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="grid max-w-md gap-3 rounded-lg border border-slate-200 bg-white p-6"
          noValidate
        >
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nome">
              Nome da equipe
            </label>
            <input
              id="nome"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("nome")}
            />
            {errors.nome && <p className="mt-1 text-sm text-red-600">{errors.nome.message}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nivel">
              Nivel da equipe
            </label>
            <select
              id="nivel"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("nivel")}
            >
              {NIVEIS.map((n) => (
                <option key={n} value={n}>
                  {rotuloNivel(n)}
                </option>
              ))}
            </select>
          </div>

          <div role="group" aria-label="Modalidades">
            <span className="mb-1 block text-sm font-medium text-slate-700">Modalidades</span>
            {modalidadesElegiveisParaCriar.length === 0 && (
              <p className="text-sm text-slate-500">
                Nenhuma modalidade compatível com este nível ainda.
              </p>
            )}
            <div className="space-y-1">
              {modalidadesElegiveisParaCriar.map((m) => (
                <label key={m.id} className="flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" value={m.id} {...register("modalidadeIds")} />
                  {m.nome}
                </label>
              ))}
            </div>
          </div>

          {erroGeral && <p className="text-sm text-red-600">{erroGeral}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-2 rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50"
          >
            Criar equipe
          </button>
        </form>
      </section>
      )}
    </main>
  );
}
