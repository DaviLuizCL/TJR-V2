import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";

const NIVEIS = [1, 2, 3, 4] as const;

const schema = z.object({
  nome: z.string().min(1, "Informe o nome da equipe"),
  nivel: z.coerce.number().int().min(1).max(4),
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
              Nivel {n}
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

export function EquipeListPage() {
  const queryClient = useQueryClient();
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [filtroNivel, setFiltroNivel] = useState<string>("");
  const [equipeEditandoId, setEquipeEditandoId] = useState<string | null>(null);
  const ehCoordenador = useAuthStore((state) => state.usuario?.papel) === "COORDENADOR";

  const { data, isLoading } = useQuery({
    queryKey: ["equipes", filtroNivel],
    queryFn: async () => {
      const query: Record<string, unknown> = { size: 100 };
      if (filtroNivel) query.nivel = Number(filtroNivel);
      const { data } = await api.GET("/api/v1/equipes", { params: { query } });
      return (data?.itens ?? []) as EquipeItem[];
    },
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema), defaultValues: { nivel: 1 } });

  async function invalidar() {
    await queryClient.invalidateQueries({ queryKey: ["equipes"] });
  }

  async function onSubmit(dados: FormData) {
    setErroGeral(null);
    // ativo tem default no backend (Pydantic), mas o openapi-typescript gera esse
    // campo como obrigatorio no tipo do payload sempre que ha um valor default.
    const { error } = await api.POST("/api/v1/equipes", { body: { ...dados, ativo: true } });

    if (error) {
      setErroGeral(extrairErro(error).mensagem);
      return;
    }

    reset({ nome: "", nivel: 1 });
    await invalidar();
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
                  Nivel {n}
                </option>
              ))}
            </select>
          </div>
        </div>

        {isLoading && <p className="text-slate-500">Carregando...</p>}
        {!isLoading && data?.length === 0 && (
          <p className="text-slate-500">Nenhuma equipe cadastrada ainda.</p>
        )}

        <ul className="space-y-2">
          {data?.map((equipe) => (
            <li
              key={equipe.id}
              className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3"
            >
              {ehCoordenador && equipeEditandoId === equipe.id ? (
                <EquipeEditForm
                  equipe={equipe}
                  onSalvar={(dados) => salvarEdicao(equipe.id, dados)}
                  onCancelar={() => setEquipeEditandoId(null)}
                />
              ) : (
                <>
                  <div>
                    <span className="font-medium text-slate-800">{equipe.nome}</span>
                    <span className="ml-2 text-sm text-slate-500">Nivel {equipe.nivel}</span>
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
                  Nivel {n}
                </option>
              ))}
            </select>
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
