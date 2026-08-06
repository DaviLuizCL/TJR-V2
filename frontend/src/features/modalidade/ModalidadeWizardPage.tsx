import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Controller, useFieldArray, useForm, type UseFormReturn } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { api, extrairErro } from "../../api/client";
import type { components } from "../../api/types";

type ModalidadeCreateBody = components["schemas"]["ModalidadeCreate"];

const TIPOS_DISPUTA = ["INDIVIDUAL", "CONFRONTO"] as const;
const FORMATOS_CHAVEAMENTO = ["MATA_MATA", "TODOS_CONTRA_TODOS"] as const;
const CONSOLIDACOES = [
  "SOMA_RODADAS",
  "MELHOR_RODADA",
  "MELHOR_N_RODADAS",
  "IGNORA_MENOR_NOTA",
] as const;
const TIPOS_DESEMPATE = [
  "MAIOR_TOTAL_EM_UMA_RODADA",
  "MENOR_TOTAL_PENALIDADES",
  "MAIOR_PONTUACAO_NO_CRITERIO",
  "MENOR_TEMPO",
] as const;
const DIRECOES_DESEMPATE = ["MAIOR", "MENOR"] as const;

const schema = z
  .object({
    nome: z.string().min(1, "Informe o nome da modalidade"),
    descricao: z.string().optional(),
    tipo_disputa: z.enum(TIPOS_DISPUTA),
    formato_chaveamento: z.enum(FORMATOS_CHAVEAMENTO).nullable().optional(),
    niveis_aplicaveis: z.array(z.number()).min(1, "Selecione ao menos um nivel"),
    ficha_unica_entre_niveis: z.boolean(),
    qtd_rodadas: z.coerce.number().int().min(1, "Deve ser pelo menos 1"),
    tentativas_por_rodada: z.coerce.number().int().min(1, "Deve ser pelo menos 1"),
    duracao_maxima_rodada_seg: z.coerce.number().int().min(1).nullable().optional(),
    pausa_entre_rodadas_seg: z.coerce.number().int().min(0).nullable().optional(),
    consolidacao: z.enum(CONSOLIDACOES),
    consolidacao_n: z.coerce.number().int().min(1).nullable().optional(),
    permite_total_negativo: z.boolean(),
    desempates: z
      .array(
        z.object({
          tipo: z.enum(TIPOS_DESEMPATE),
          direcao: z.enum(DIRECOES_DESEMPATE),
          criterio_id: z.string().nullable().optional(),
        }),
      )
      .optional(),
    arenas: z
      .array(
        z.object({
          nome: z.string().min(1, "Informe o nome da arena"),
          niveis_aplicaveis: z.array(z.number()).optional(),
        }),
      )
      .optional(),
  })
  .superRefine((dados, ctx) => {
    if (dados.formato_chaveamento && dados.tipo_disputa !== "CONFRONTO") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Formato de chaveamento so e valido quando o tipo de disputa e confronto",
        path: ["formato_chaveamento"],
      });
    }
    if (dados.consolidacao === "MELHOR_N_RODADAS") {
      if (!dados.consolidacao_n) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Informe quantas rodadas contam para a nota final",
          path: ["consolidacao_n"],
        });
      } else if (dados.consolidacao_n > dados.qtd_rodadas) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Nao pode ser maior que a quantidade de rodadas",
          path: ["consolidacao_n"],
        });
      }
    }
  });

type FormData = z.infer<typeof schema>;

const VALORES_PADRAO: FormData = {
  nome: "",
  descricao: "",
  tipo_disputa: "INDIVIDUAL",
  formato_chaveamento: null,
  niveis_aplicaveis: [],
  ficha_unica_entre_niveis: false,
  qtd_rodadas: 1,
  tentativas_por_rodada: 1,
  duracao_maxima_rodada_seg: null,
  pausa_entre_rodadas_seg: null,
  consolidacao: "SOMA_RODADAS",
  consolidacao_n: null,
  permite_total_negativo: false,
  desempates: [],
  arenas: [],
};

const TITULOS_ETAPAS = [
  "Dados basicos",
  "Tipo de disputa",
  "Niveis e ficha unica",
  "Rodadas e duracao",
  "Consolidacao e desempates",
];

const CAMPOS_POR_ETAPA: (keyof FormData)[][] = [
  ["nome", "descricao"],
  ["tipo_disputa", "formato_chaveamento"],
  ["niveis_aplicaveis", "ficha_unica_entre_niveis"],
  [
    "qtd_rodadas",
    "tentativas_por_rodada",
    "duracao_maxima_rodada_seg",
    "pausa_entre_rodadas_seg",
    "arenas",
  ],
  ["consolidacao", "consolidacao_n", "permite_total_negativo", "desempates"],
];

function EtapaDadosBasicos({ form }: { form: UseFormReturn<FormData> }) {
  const {
    register,
    formState: { errors },
  } = form;
  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="nome">
          Nome da modalidade
        </label>
        <input
          id="nome"
          className="w-full rounded border border-slate-300 px-3 py-2"
          {...register("nome")}
        />
        {errors.nome && <p className="mt-1 text-sm text-red-600">{errors.nome.message}</p>}
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="descricao">
          Descricao (opcional)
        </label>
        <textarea
          id="descricao"
          className="w-full rounded border border-slate-300 px-3 py-2"
          rows={3}
          {...register("descricao")}
        />
      </div>
    </div>
  );
}

function EtapaTipoDisputa({ form }: { form: UseFormReturn<FormData> }) {
  const { register, watch } = form;
  const tipoDisputa = watch("tipo_disputa");

  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="mb-2 text-sm font-medium text-slate-700">Tipo de disputa</legend>
        <label className="mr-4 inline-flex items-center gap-2">
          <input type="radio" value="INDIVIDUAL" {...register("tipo_disputa")} />
          Individual
        </label>
        <label className="inline-flex items-center gap-2">
          <input type="radio" value="CONFRONTO" {...register("tipo_disputa")} />
          Confronto
        </label>
      </fieldset>

      {tipoDisputa === "CONFRONTO" && (
        <div>
          <label
            className="mb-1 block text-sm font-medium text-slate-700"
            htmlFor="formato_chaveamento"
          >
            Formato de chaveamento
          </label>
          <select
            id="formato_chaveamento"
            className="w-full rounded border border-slate-300 px-3 py-2"
            {...register("formato_chaveamento")}
          >
            <option value="">Definir depois</option>
            <option value="MATA_MATA">Mata-mata</option>
            <option value="TODOS_CONTRA_TODOS">Todos contra todos</option>
          </select>
        </div>
      )}
    </div>
  );
}

function EtapaNiveis({ form }: { form: UseFormReturn<FormData> }) {
  const { control, register, setValue, watch } = form;
  const fichaUnica = watch("ficha_unica_entre_niveis");

  return (
    <div className="space-y-4">
      {fichaUnica ? (
        <p className="text-sm text-slate-600">
          Todos os niveis (1 a 4) estao incluidos automaticamente, pois a ficha e unica entre
          niveis.
        </p>
      ) : (
        <Controller
          control={control}
          name="niveis_aplicaveis"
          render={({ field, fieldState }) => (
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-slate-700">
                Niveis aplicaveis
              </legend>
              <div className="flex gap-4">
                {[1, 2, 3, 4].map((nivel) => (
                  <label key={nivel} className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={field.value?.includes(nivel) ?? false}
                      onChange={(evento) => {
                        const atual = field.value ?? [];
                        field.onChange(
                          evento.target.checked
                            ? [...atual, nivel]
                            : atual.filter((n) => n !== nivel),
                        );
                      }}
                    />
                    Nivel {nivel}
                  </label>
                ))}
              </div>
              {fieldState.error && (
                <p className="mt-1 text-sm text-red-600">{fieldState.error.message}</p>
              )}
            </fieldset>
          )}
        />
      )}

      <label className="inline-flex items-center gap-2">
        <input
          type="checkbox"
          {...register("ficha_unica_entre_niveis", {
            onChange: (evento) => {
              setValue(
                "niveis_aplicaveis",
                evento.target.checked ? [1, 2, 3, 4] : [],
                { shouldValidate: true },
              );
            },
          })}
        />
        Usar uma unica ficha para todos os niveis
      </label>
    </div>
  );
}

function EtapaArenas({ form }: { form: UseFormReturn<FormData> }) {
  const { control, register, watch } = form;
  const { fields, append, remove } = useFieldArray({ control, name: "arenas" });
  const niveisDaModalidade = watch("niveis_aplicaveis") ?? [];

  return (
    <div className="mt-6 border-t border-slate-200 pt-4">
      <p className="mb-1 text-sm font-medium text-slate-700">Arenas</p>
      <p className="mb-3 text-xs text-slate-500">
        Opcional aqui: da pra criar depois na aba Horarios. Nenhum nivel marcado = arena atende
        todos os niveis da modalidade.
      </p>
      <div className="space-y-3">
        {fields.map((field, index) => (
          <div
            key={field.id}
            className="flex flex-wrap items-end gap-3 rounded border border-slate-200 p-3"
          >
            <div>
              <label
                className="mb-1 block text-xs text-slate-600"
                htmlFor={`arenas.${index}.nome`}
              >
                Nome da arena
              </label>
              <input
                id={`arenas.${index}.nome`}
                className="rounded border border-slate-300 px-2 py-1"
                {...register(`arenas.${index}.nome` as const)}
              />
            </div>
            <Controller
              control={control}
              name={`arenas.${index}.niveis_aplicaveis`}
              render={({ field: campoNiveis }) => (
                <fieldset>
                  <legend className="mb-1 text-xs text-slate-600">Niveis atendidos</legend>
                  <div className="flex gap-3">
                    {niveisDaModalidade.map((nivel) => (
                      <label key={nivel} className="inline-flex items-center gap-1 text-sm">
                        <input
                          type="checkbox"
                          checked={campoNiveis.value?.includes(nivel) ?? false}
                          onChange={(evento) => {
                            const atual = campoNiveis.value ?? [];
                            campoNiveis.onChange(
                              evento.target.checked
                                ? [...atual, nivel]
                                : atual.filter((n) => n !== nivel),
                            );
                          }}
                        />
                        Atende nivel {nivel}
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}
            />
            <button
              type="button"
              onClick={() => remove(index)}
              className="rounded border border-red-300 px-3 py-1 text-sm text-red-700"
            >
              Remover
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => append({ nome: "", niveis_aplicaveis: [] })}
        className="mt-3 rounded border border-slate-300 px-3 py-1 text-sm text-slate-700"
      >
        Adicionar arena
      </button>
    </div>
  );
}

function EtapaRodadas({
  form,
  modoEdicao,
}: {
  form: UseFormReturn<FormData>;
  modoEdicao: boolean;
}) {
  const {
    register,
    watch,
    formState: { errors },
  } = form;
  const tipoDisputa = watch("tipo_disputa");

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="qtd_rodadas">
          Quantidade de rodadas
        </label>
        <input
          id="qtd_rodadas"
          type="number"
          className="w-full rounded border border-slate-300 px-3 py-2"
          {...register("qtd_rodadas")}
        />
        {errors.qtd_rodadas && (
          <p className="mt-1 text-sm text-red-600">{errors.qtd_rodadas.message}</p>
        )}
      </div>
      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="tentativas_por_rodada"
        >
          Tentativas por rodada
        </label>
        <input
          id="tentativas_por_rodada"
          type="number"
          className="w-full rounded border border-slate-300 px-3 py-2"
          {...register("tentativas_por_rodada")}
        />
        {errors.tentativas_por_rodada && (
          <p className="mt-1 text-sm text-red-600">{errors.tentativas_por_rodada.message}</p>
        )}
      </div>
      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="duracao_maxima_rodada_seg"
        >
          Duracao maxima da rodada (segundos, opcional)
        </label>
        <input
          id="duracao_maxima_rodada_seg"
          type="number"
          className="w-full rounded border border-slate-300 px-3 py-2"
          {...register("duracao_maxima_rodada_seg")}
        />
      </div>
      <div>
        <label
          className="mb-1 block text-sm font-medium text-slate-700"
          htmlFor="pausa_entre_rodadas_seg"
        >
          Pausa entre rodadas (segundos, opcional)
        </label>
        <input
          id="pausa_entre_rodadas_seg"
          type="number"
          className="w-full rounded border border-slate-300 px-3 py-2"
          {...register("pausa_entre_rodadas_seg")}
        />
      </div>

      {tipoDisputa === "INDIVIDUAL" && !modoEdicao && <EtapaArenas form={form} />}
    </div>
  );
}

function EtapaDesempates({ form }: { form: UseFormReturn<FormData> }) {
  const { control, register } = form;
  const { fields, append, remove } = useFieldArray({ control, name: "desempates" });

  return (
    <div>
      <p className="mb-2 text-sm font-medium text-slate-700">Regras de desempate</p>
      <div className="space-y-3">
        {fields.map((field, index) => (
          <div
            key={field.id}
            className="flex items-end gap-2 rounded border border-slate-200 p-3"
          >
            <div>
              <label
                className="mb-1 block text-xs text-slate-600"
                htmlFor={`desempates.${index}.tipo`}
              >
                Criterio de desempate
              </label>
              <select
                id={`desempates.${index}.tipo`}
                className="rounded border border-slate-300 px-2 py-1"
                {...register(`desempates.${index}.tipo` as const)}
              >
                {TIPOS_DESEMPATE.map((tipo) => (
                  <option key={tipo} value={tipo}>
                    {tipo}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                className="mb-1 block text-xs text-slate-600"
                htmlFor={`desempates.${index}.direcao`}
              >
                Direcao
              </label>
              <select
                id={`desempates.${index}.direcao`}
                className="rounded border border-slate-300 px-2 py-1"
                {...register(`desempates.${index}.direcao` as const)}
              >
                {DIRECOES_DESEMPATE.map((direcao) => (
                  <option key={direcao} value={direcao}>
                    {direcao}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={() => remove(index)}
              className="rounded border border-red-300 px-3 py-1 text-sm text-red-700"
            >
              Remover
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => append({ tipo: "MAIOR_TOTAL_EM_UMA_RODADA", direcao: "MAIOR" })}
        className="mt-3 rounded border border-slate-300 px-3 py-1 text-sm text-slate-700"
      >
        Adicionar regra de desempate
      </button>
    </div>
  );
}

function EtapaConsolidacao({ form }: { form: UseFormReturn<FormData> }) {
  const {
    register,
    watch,
    formState: { errors },
  } = form;
  const consolidacao = watch("consolidacao");

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="consolidacao">
          Como consolidar as rodadas
        </label>
        <select
          id="consolidacao"
          className="w-full rounded border border-slate-300 px-3 py-2"
          {...register("consolidacao")}
        >
          <option value="SOMA_RODADAS">Soma das rodadas</option>
          <option value="MELHOR_RODADA">Melhor rodada</option>
          <option value="MELHOR_N_RODADAS">Melhores N rodadas</option>
          <option value="IGNORA_MENOR_NOTA">Ignorar menor nota</option>
        </select>
        {consolidacao === "IGNORA_MENOR_NOTA" && (
          <p className="mt-1 text-sm text-slate-500">
            A nota final soma o total de todas as rodadas, exceto a de menor pontuacao.
          </p>
        )}
      </div>

      {consolidacao === "MELHOR_N_RODADAS" && (
        <div>
          <label
            className="mb-1 block text-sm font-medium text-slate-700"
            htmlFor="consolidacao_n"
          >
            Quantas rodadas contam
          </label>
          <input
            id="consolidacao_n"
            type="number"
            className="w-full rounded border border-slate-300 px-3 py-2"
            {...register("consolidacao_n")}
          />
          {errors.consolidacao_n && (
            <p className="mt-1 text-sm text-red-600">{errors.consolidacao_n.message}</p>
          )}
        </div>
      )}

      <label className="inline-flex items-center gap-2">
        <input type="checkbox" {...register("permite_total_negativo")} />
        Permitir total negativo
      </label>

      <EtapaDesempates form={form} />
    </div>
  );
}

export function ModalidadeWizardPage() {
  const { eventoId, modalidadeId } = useParams<{ eventoId: string; modalidadeId?: string }>();
  const modoEdicao = !!modalidadeId;
  const navigate = useNavigate();
  const [etapa, setEtapa] = useState(0);
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  const { data: modalidadeExistente } = useQuery({
    queryKey: ["modalidade", modalidadeId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/modalidades/{modalidade_id}", {
        params: { path: { modalidade_id: modalidadeId! } },
      });
      return data;
    },
    enabled: modoEdicao,
  });

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: VALORES_PADRAO,
  });

  useEffect(() => {
    if (modalidadeExistente) {
      form.reset({
        nome: modalidadeExistente.nome,
        descricao: modalidadeExistente.descricao ?? "",
        tipo_disputa: modalidadeExistente.tipo_disputa,
        formato_chaveamento: modalidadeExistente.formato_chaveamento,
        niveis_aplicaveis: modalidadeExistente.niveis_aplicaveis,
        ficha_unica_entre_niveis: modalidadeExistente.ficha_unica_entre_niveis,
        qtd_rodadas: modalidadeExistente.qtd_rodadas,
        tentativas_por_rodada: modalidadeExistente.tentativas_por_rodada,
        duracao_maxima_rodada_seg: modalidadeExistente.duracao_maxima_rodada_seg,
        pausa_entre_rodadas_seg: modalidadeExistente.pausa_entre_rodadas_seg,
        consolidacao: modalidadeExistente.consolidacao,
        consolidacao_n: modalidadeExistente.consolidacao_n,
        permite_total_negativo: modalidadeExistente.permite_total_negativo,
        desempates: modalidadeExistente.desempates ?? [],
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modalidadeExistente]);

  async function avancar() {
    const valido = await form.trigger(CAMPOS_POR_ETAPA[etapa]);
    if (valido) setEtapa((e) => Math.min(e + 1, TITULOS_ETAPAS.length - 1));
  }

  function voltar() {
    setEtapa((e) => Math.max(e - 1, 0));
  }

  async function onSubmit(dados: FormData) {
    setErroGeral(null);

    const resultado = modoEdicao
      ? await api.PATCH("/api/v1/modalidades/{modalidade_id}", {
          params: { path: { modalidade_id: modalidadeId! } },
          body: dados,
        })
      : await api.POST("/api/v1/modalidades", {
          // pontos_vitoria/pontos_empate tem default no backend (Pydantic) e por isso nao
          // sao obrigatorios na API, mas o openapi-typescript gera esses campos como
          // obrigatorios no tipo do payload sempre que ha um valor default. O wizard nao
          // coleta esses campos ainda; o backend assume os defaults quando nao enviados.
          body: { ...dados, evento_id: eventoId! } as unknown as ModalidadeCreateBody,
        });

    if (resultado.error) {
      setErroGeral(extrairErro(resultado.error).mensagem);
      return;
    }

    if (!modoEdicao && dados.tipo_disputa === "INDIVIDUAL") {
      const modalidadeId = (resultado.data as { id: string }).id;

      const resultadoRodadas = await api.POST("/api/v1/rodadas/gerar", {
        body: { modalidade_id: modalidadeId },
      });
      if (resultadoRodadas.error) {
        setErroGeral(
          `Modalidade criada, mas falha ao gerar rodadas: ${extrairErro(resultadoRodadas.error).mensagem}`,
        );
        return;
      }

      for (const arena of dados.arenas ?? []) {
        const resultadoArena = await api.POST("/api/v1/arenas", {
          body: {
            modalidade_id: modalidadeId,
            nome: arena.nome,
            niveis_aplicaveis:
              arena.niveis_aplicaveis && arena.niveis_aplicaveis.length > 0
                ? arena.niveis_aplicaveis
                : null,
            ativo: true,
          },
        });
        if (resultadoArena.error) {
          setErroGeral(
            `Modalidade e rodadas criadas, mas falha ao criar a arena "${arena.nome}": ${extrairErro(resultadoArena.error).mensagem}`,
          );
          return;
        }
      }
    }

    navigate(`/eventos/${eventoId}/modalidades`);
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="mb-2 text-2xl font-semibold text-slate-800">
        {modoEdicao ? "Editar modalidade" : "Nova modalidade"}
      </h1>
      <p className="mb-6 text-sm text-slate-500">
        Passo {etapa + 1} de {TITULOS_ETAPAS.length}: {TITULOS_ETAPAS[etapa]}
      </p>

      <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
        {etapa === 0 && <EtapaDadosBasicos form={form} />}
        {etapa === 1 && <EtapaTipoDisputa form={form} />}
        {etapa === 2 && <EtapaNiveis form={form} />}
        {etapa === 3 && <EtapaRodadas form={form} modoEdicao={modoEdicao} />}
        {etapa === 4 && <EtapaConsolidacao form={form} />}

        {erroGeral && <p className="mt-4 text-sm text-red-600">{erroGeral}</p>}

        <div className="mt-6 flex justify-between">
          <button
            type="button"
            onClick={voltar}
            disabled={etapa === 0}
            className="rounded border border-slate-300 px-4 py-2 disabled:opacity-50"
          >
            Voltar
          </button>
          {etapa < TITULOS_ETAPAS.length - 1 ? (
            <button
              type="button"
              onClick={avancar}
              className="rounded bg-slate-800 px-4 py-2 font-medium text-white"
            >
              Avancar
            </button>
          ) : (
            <button
              type="submit"
              disabled={form.formState.isSubmitting}
              className="rounded bg-slate-800 px-4 py-2 font-medium text-white disabled:opacity-50"
            >
              {modoEdicao ? "Salvar" : "Criar modalidade"}
            </button>
          )}
        </div>
      </form>
    </main>
  );
}
