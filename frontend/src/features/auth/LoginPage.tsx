import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";

const schema = z.object({
  email: z.string().email("Informe um e-mail valido"),
  senha: z.string().min(1, "Informe a senha"),
});

type FormData = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const definirSessao = useAuthStore((state) => state.definirSessao);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(dados: FormData) {
    setErroGeral(null);

    const { data, error } = await api.POST("/api/v1/auth/login", { body: dados });

    if (error || !data) {
      setErroGeral(extrairErro(error).mensagem);
      return;
    }

    const me = await api.GET("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });

    definirSessao({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      usuario: me.data ?? { id: "", nome: "", email: dados.email, papel: "" },
    });

    navigate("/eventos");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="w-full max-w-sm rounded-lg bg-white p-8 shadow"
        noValidate
      >
        <h1 className="mb-6 text-xl font-semibold text-slate-800">Entrar no TJR</h1>

        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
          E-mail
        </label>
        <input
          id="email"
          type="email"
          className="mb-1 w-full rounded border border-slate-300 px-3 py-2"
          {...register("email")}
        />
        {errors.email && <p className="mb-3 text-sm text-red-600">{errors.email.message}</p>}

        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="senha">
          Senha
        </label>
        <input
          id="senha"
          type="password"
          className="mb-1 w-full rounded border border-slate-300 px-3 py-2"
          {...register("senha")}
        />
        {errors.senha && <p className="mb-3 text-sm text-red-600">{errors.senha.message}</p>}

        {erroGeral && <p className="mb-3 text-sm text-red-600">{erroGeral}</p>}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-2 w-full rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          Entrar
        </button>
      </form>
    </main>
  );
}
