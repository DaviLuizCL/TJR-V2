import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import { CampoSenha } from "../../components/CampoSenha";

const PAPEIS = ["ARBITRO", "SECRETARIA", "COORDENADOR"] as const;

const schema = z.object({
  nome: z.string().min(1, "Informe o nome"),
  email: z.string().email("Informe um e-mail valido"),
  senha: z.string().min(6, "A senha precisa de pelo menos 6 caracteres"),
  papel: z.enum(PAPEIS),
});

type FormData = z.infer<typeof schema>;

interface UsuarioItem {
  id: string;
  nome: string;
  email: string;
  papel: string;
  ativo: boolean;
}

export function UsuarioListPage() {
  const queryClient = useQueryClient();
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["usuarios"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/usuarios", { params: { query: { size: 100 } } });
      return (data?.itens ?? []) as UsuarioItem[];
    },
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema), defaultValues: { papel: "ARBITRO" } });

  async function onSubmit(dados: FormData) {
    setErroGeral(null);
    const { error } = await api.POST("/api/v1/usuarios", { body: dados });

    if (error) {
      setErroGeral(extrairErro(error).mensagem);
      return;
    }

    reset({ nome: "", email: "", senha: "", papel: "ARBITRO" });
    await queryClient.invalidateQueries({ queryKey: ["usuarios"] });
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Staff</h1>

      <section className="mb-10 rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-sm font-medium uppercase tracking-wide text-slate-500">
          Cadastrar árbitro ou secretaria
        </h2>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nome">
              Nome
            </label>
            <input
              id="nome"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("nome")}
            />
            {errors.nome && <p className="mt-1 text-sm text-red-600">{errors.nome.message}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
              E-mail
            </label>
            <input
              id="email"
              type="email"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("email")}
            />
            {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>}
          </div>

          <CampoSenha
            id="senha"
            label="Senha"
            registro={register("senha")}
            erro={errors.senha?.message}
            ajuda="Passe essa senha pra pessoa pessoalmente — ela pode trocar depois."
          />

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="papel">
              Papel
            </label>
            <select
              id="papel"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("papel")}
            >
              {PAPEIS.map((papel) => (
                <option key={papel} value={papel}>
                  {papel}
                </option>
              ))}
            </select>
          </div>

          {erroGeral && <p className="text-sm text-red-600 sm:col-span-2">{erroGeral}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50 sm:col-span-2 sm:w-fit"
          >
            {isSubmitting ? "Cadastrando..." : "Cadastrar"}
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Usuários cadastrados
        </h2>
        {isLoading && <p className="text-slate-500">Carregando...</p>}
        {!isLoading && data?.length === 0 && (
          <p className="text-slate-500">Nenhum usuário cadastrado ainda.</p>
        )}
        <ul className="space-y-2">
          {data?.map((usuario) => (
            <li
              key={usuario.id}
              className="flex items-center justify-between rounded border border-slate-200 bg-white px-4 py-3"
            >
              <div>
                <span className="font-medium text-slate-800">{usuario.nome}</span>
                <span className="ml-2 text-sm text-slate-500">{usuario.email}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                  {usuario.papel}
                </span>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    usuario.ativo ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {usuario.ativo ? "Ativo" : "Inativo"}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
