import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import { Aviso } from "../../components/Aviso";
import { CampoSenha } from "../../components/CampoSenha";

const schema = z
  .object({
    nome: z.string().trim().min(1, "Informe seu nome"),
    email: z.string().email("Informe um e-mail válido"),
    senha: z.string().min(6, "A senha precisa ter pelo menos 6 caracteres"),
    confirmacao: z.string(),
  })
  .refine((dados) => dados.senha === dados.confirmacao, {
    message: "As senhas não são iguais",
    path: ["confirmacao"],
  });

type FormData = z.infer<typeof schema>;

const MENSAGENS_ERRO: Record<string, string> = {
  EMAIL_JA_CADASTRADO:
    "Este e-mail já tem conta. Volte e use Entrar; se esqueceu a senha, peça pra coordenação trocar.",
  SOLICITACAO_JA_PENDENTE:
    "Já existe um pedido com este e-mail esperando aprovação. Avise a coordenação no grupo dos juízes.",
};

// Juiz sem conta pede acesso aqui (sem login, sem e-mail de confirmacao).
// Nada e liberado ate a coordenacao aprovar em Juizes e senhas.
export function PedirAcessoPage() {
  const [enviado, setEnviado] = useState(false);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit({ nome, email, senha }: FormData) {
    setErroGeral(null);
    const { error } = await api.POST("/api/v1/solicitacoes-acesso", {
      body: { nome, email, senha },
    });
    if (error) {
      const { codigo, mensagem } = extrairErro(error);
      setErroGeral(MENSAGENS_ERRO[codigo] ?? mensagem);
      return;
    }
    setEnviado(true);
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

      <div className="card w-full max-w-sm border-neon/30 p-8 shadow-glow">
        <h1 className="mb-2 text-2xl font-bold">Pedir acesso de juiz</h1>

        {enviado ? (
          <>
            <Aviso tipo="sucesso" className="mb-4">
              Pedido enviado! Agora avise a coordenação no grupo dos juízes. Quando aprovarem, é só
              entrar com este e-mail e a senha que você escolheu.
            </Aviso>
            <Link to="/login" className="btn-secondary min-h-12 w-full text-base">
              Voltar pro login
            </Link>
          </>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <p className="mb-5 text-sm text-slate-500">
              Preencha seus dados. A coordenação confere e libera sua conta.
            </p>

            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nome">
              Nome completo
            </label>
            <input
              id="nome"
              autoComplete="name"
              className="mb-1 min-h-12 w-full rounded-lg border border-slate-300 px-3 py-2"
              {...register("nome")}
            />
            {errors.nome && <p className="mb-3 text-sm text-red-600">{errors.nome.message}</p>}

            <label className="mb-1 mt-3 block text-sm font-medium text-slate-700" htmlFor="email">
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

            <div className="mt-3">
              <CampoSenha
                id="senha"
                label="Senha"
                registro={register("senha")}
                erro={errors.senha?.message}
              />
            </div>
            <div className="mb-3 mt-3">
              <CampoSenha
                id="confirmacao"
                label="Repita a senha"
                registro={register("confirmacao")}
                erro={errors.confirmacao?.message}
              />
            </div>

            {erroGeral && (
              <Aviso tipo="erro" className="mb-3">
                {erroGeral}
              </Aviso>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary mt-2 min-h-12 w-full text-base"
            >
              {isSubmitting ? "Enviando..." : "Enviar pedido"}
            </button>
            <p className="mt-4 text-center text-sm">
              <Link to="/login" className="text-slate-500 hover:text-neon">
                Já tenho conta → Entrar
              </Link>
            </p>
          </form>
        )}
      </div>
    </main>
  );
}
