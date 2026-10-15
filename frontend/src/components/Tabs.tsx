export interface TabItem<T extends string> {
  valor: T;
  rotulo: string;
  icone?: string;
}

interface TabsProps<T extends string> {
  itens: TabItem<T>[];
  valor: T;
  onChange: (valor: T) => void;
  tamanho?: "grande" | "pequeno";
}

// Abas em formato "pilula" (segmented control). Mantem role=tablist/tab pra
// leitor de tela e pros testes que procuram aba por nome.
export function Tabs<T extends string>({ itens, valor, onChange, tamanho = "grande" }: TabsProps<T>) {
  const grande = tamanho === "grande";
  const altura = grande ? "min-h-12 px-5 text-base" : "min-h-10 px-3 text-sm";
  const ativaClasse = grande
    ? "bg-neon text-slate-50 shadow-glow"
    : "bg-slate-200 text-neon ring-1 ring-neon/40";

  return (
    <div
      role="tablist"
      className={`mb-6 inline-flex max-w-full flex-wrap gap-1 rounded-xl p-1 ${
        grande ? "border border-slate-200 bg-slate-100/80" : ""
      }`}
    >
      {itens.map((item) => {
        const ativa = item.valor === valor;
        return (
          <button
            key={item.valor}
            role="tab"
            type="button"
            aria-selected={ativa}
            onClick={() => onChange(item.valor)}
            className={`${altura} inline-flex items-center gap-2 rounded-lg font-display font-bold uppercase tracking-wider ${
              ativa
                ? ativaClasse
                : "text-slate-500 hover:bg-slate-200 hover:text-slate-800"
            }`}
          >
            {item.icone && <span aria-hidden="true">{item.icone}</span>}
            {item.rotulo}
          </button>
        );
      })}
    </div>
  );
}
