import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { CampoSenha } from "../../components/CampoSenha";
import { useAuthStore } from "../../lib/auth-store";

const schema = z.object({
  email: z.string().email("Informe um e-mail válido"),
  senha: z.string().min(1, "Informe a senha"),
});

type FormData = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const definirSessao = useAuthStore((state) => state.definirSessao);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [aguardandoAprovacao, setAguardandoAprovacao] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(dados: FormData) {
    setErroGeral(null);
    setAguardandoAprovacao(false);

    const { data, error } = await api.POST("/api/v1/auth/login", { body: dados });

    if (error || !data) {
      const erro = extrairErro(error);
      if (erro.codigo === "ACESSO_AGUARDANDO_APROVACAO") {
        setAguardandoAprovacao(true);
      } else {
        setErroGeral(erro.mensagem);
      }
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

    // O sistema so suporta um evento (TJR 2026, ver EVENTO_UNICO_JA_EXISTE) --
    // pula a tela de selecao e vai direto pro fluxo operacional, como se o
    // usuario ja tivesse clicado no evento. Sem evento cadastrado ainda
    // (banco recem-criado, antes do seed), cai de volta pra /eventos.
    const eventos = await api.GET("/api/v1/eventos", { params: { query: { size: 1 } } });
    const evento = eventos.data?.itens?.[0];

    navigate(evento ? `/eventos/${evento.id}/competicoes` : "/eventos");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="mb-8 text-center">
        <p className="text-6xl" aria-hidden="true">
          🤖
        </p>
        <p className="mt-2 bg-gradient-to-r from-neon to-plasma bg-clip-text font-display text-6xl font-bold tracking-[0.3em] text-transparent">
          TJR
        </p>
        <p className="eyebrow mt-1 text-slate-500">Torneio Juvenil de Robótica</p>
      </div>
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="card w-full max-w-sm border-neon/30 p-8 shadow-glow"
        noValidate
      >
        <h1 className="mb-6 text-2xl font-bold">Entrar no TJR</h1>

        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
          E-mail
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          className="mb-1 min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2"
          {...register("email")}
        />
        {errors.email && <p className="mb-3 text-sm text-red-600">{errors.email.message}</p>}

        <div className="mb-3 mt-3">
          <CampoSenha
            id="senha"
            label="Senha"
            registro={register("senha")}
            erro={errors.senha?.message}
          />
        </div>

        {erroGeral && (
          <Aviso tipo="erro" className="mb-3">
            {erroGeral}
          </Aviso>
        )}
        {aguardandoAprovacao && (
          <Aviso tipo="info" className="mb-3">
            Seu pedido de acesso ainda não foi aprovado. Avise a coordenação no grupo dos juízes.
          </Aviso>
        )}

        <button type="submit" disabled={isSubmitting} className="btn-primary mt-2 min-h-12 w-full text-base">
          {isSubmitting ? "Entrando..." : "Entrar"}
        </button>
        <p className="mt-4 text-center text-xs text-slate-500">
          Esqueceu a senha? Peça pra coordenação trocar em Administração → Juízes e senhas.
        </p>
        <p className="mt-3 border-t border-slate-200 pt-3 text-center text-sm text-slate-600">
          Sou juiz e ainda não tenho conta →{" "}
          <Link to="/pedir-acesso" className="font-semibold text-neon hover:underline">
            Pedir acesso
          </Link>
        </p>
      </form>
    </main>
  );
}
