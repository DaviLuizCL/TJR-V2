import { baseUrl } from "../api/client";
import type { components } from "../api/types";

export type TipoRegra = components["schemas"]["TipoRegra"];
export type ModalidadeComRegras = components["schemas"]["ModalidadeComRegrasOut"];

// Os dois PDFs de cada modalidade, na ordem em que aparecem na tela.
export const TIPOS_REGRA: { tipo: TipoRegra; rotulo: string; descricao: string }[] = [
  { tipo: "MANUAL", rotulo: "Manual completo", descricao: "Todas as regras da modalidade" },
  { tipo: "CADERNO_ALUNO", rotulo: "Caderninho do aluno", descricao: "Resumo pra equipe" },
];

// Link direto (sem login) que abre o PDF no navegador.
export function urlRegra(modalidadeId: string, tipo: TipoRegra): string {
  return `${baseUrl}/api/v1/publico/modalidades/${modalidadeId}/regras/${tipo}`;
}
