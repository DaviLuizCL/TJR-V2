// Icone decorativo por modalidade, so pra leitura rapida na tela. Casado por
// palavra-chave no nome (modalidade e dado, nao codigo): modalidade nova sem
// palavra conhecida cai no robo.
const REGRAS: [RegExp, string][] = [
  [/sum[oô]/i, "🥋"],
  [/cabo de guerra/i, "🪢"],
  [/corrida|carro/i, "🏎️"],
  [/dan[cç]a/i, "💃"],
  [/alto risco/i, "🧗"],
  [/resgate/i, "🚑"],
  [/viagem|centro da terra/i, "🌋"],
];

export function iconeModalidade(nome: string): string {
  return REGRAS.find(([regra]) => regra.test(nome))?.[1] ?? "🤖";
}
