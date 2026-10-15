import type { ReactNode } from "react";

const TONS = {
  neutro: "border-slate-300",
  aviso: "border-amber-400",
  sucesso: "border-emerald-400",
};

// Barra presa no rodape da tela (total da nota + botao principal). O arbitro
// lanca de pe, no celular: o total tem que estar sempre a vista (CLAUDE.md, secao 10).
// Quem usa precisa dar padding-bottom no conteudo pra barra nao cobrir o fim da pagina.
export function BarraFixa({
  children,
  tom = "neutro",
}: {
  children: ReactNode;
  tom?: keyof typeof TONS;
}) {
  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-20 border-t-2 bg-slate-50/95 backdrop-blur ${TONS[tom]}`}
    >
      <div className="mx-auto flex max-w-2xl items-center gap-4 px-4 py-3 sm:px-6">{children}</div>
    </div>
  );
}
