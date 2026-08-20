import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import { useAuthStore } from "../../lib/auth-store";

const schema = z
  .object({
    nome: z.string().trim().min(1, "Informe o nome do evento"),
    ano: z.coerce.number().int("Ano invalido"),
    data_inicio: z.string().min(1, "Informe a data de inicio"),
    data_fim: z.string().min(1, "Informe a data de fim"),
  })
  .refine((dados) => dados.data_fim >= dados.data_inicio, {
    message: "Data de fim nao pode ser anterior a data de inicio",
    path: ["data_fim"],
  });

type FormData = z.infer<typeof schema>;

export function EventoSelectPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const papel = useAuthStore((state) => state.usuario?.papel);
  const ehCoordenador = papel === "COORDENADOR";
  const ehArbitro = papel === "ARBITRO";
  // Arbitro so usa a tela de Pontuar - mandar pra /modalidades (area
  // administrativa) so exporia links/acoes que ele nao pode usar (ver
  // mesma logica em components/Header.tsx).
  function destinoDoEvento(eventoId: string): string {
    return ehArbitro ? `/eventos/${eventoId}/individual` : `/eventos/${eventoId}/modalidades`;
  }

  const { data, isLoading } = useQuery({
    queryKey: ["eventos"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/eventos", { params: { query: { size: 50 } } });
      return data?.itens ?? [];
    },
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(dados: FormData) {
    setErroGeral(null);
    const { data: criado, error } = await api.POST("/api/v1/eventos", { body: dados });

    if (error || !criado) {
      setErroGeral(extrairErro(error).mensagem);
      return;
    }

    reset();
    await queryClient.invalidateQueries({ queryKey: ["eventos"] });
    navigate(`/eventos/${criado.id}/modalidades`);
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-2xl font-semibold text-slate-800">Eventos</h1>

      <section className="mb-10">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Selecionar um evento
        </h2>
        {isLoading && <p className="text-slate-500">Carregando...</p>}
        {!isLoading && data?.length === 0 && (
          <p className="text-slate-500">Nenhum evento cadastrado ainda.</p>
        )}
        <ul className="space-y-2">
          {data?.map((evento) => (
            <li key={evento.id}>
              <Link
                to={destinoDoEvento(evento.id)}
                className="block rounded border border-slate-200 bg-white px-4 py-3 hover:border-slate-400"
              >
                <span className="font-medium text-slate-800">{evento.nome}</span>
                <span className="ml-2 text-sm text-slate-500">
                  {evento.ano} · {evento.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {ehCoordenador && (
      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Criar novo evento
        </h2>
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="grid max-w-md gap-3 rounded-lg border border-slate-200 bg-white p-6"
          noValidate
        >
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nome">
              Nome do evento
            </label>
            <input
              id="nome"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("nome")}
            />
            {errors.nome && <p className="mt-1 text-sm text-red-600">{errors.nome.message}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="ano">
              Ano
            </label>
            <input
              id="ano"
              type="number"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("ano")}
            />
            {errors.ano && <p className="mt-1 text-sm text-red-600">{errors.ano.message}</p>}
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="data_inicio"
            >
              Data de inicio
            </label>
            <input
              id="data_inicio"
              type="date"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("data_inicio")}
            />
            {errors.data_inicio && (
              <p className="mt-1 text-sm text-red-600">{errors.data_inicio.message}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="data_fim">
              Data de fim
            </label>
            <input
              id="data_fim"
              type="date"
              className="w-full rounded border border-slate-300 px-3 py-2"
              {...register("data_fim")}
            />
            {errors.data_fim && (
              <p className="mt-1 text-sm text-red-600">{errors.data_fim.message}</p>
            )}
          </div>

          {erroGeral && <p className="text-sm text-red-600">{erroGeral}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-2 rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50"
          >
            Criar evento
          </button>
        </form>
      </section>
      )}
    </main>
  );
}
