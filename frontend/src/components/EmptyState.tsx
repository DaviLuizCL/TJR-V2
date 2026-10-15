import type { ReactNode } from "react";

interface EmptyStateProps {
  icone?: string;
  titulo: string;
  children?: ReactNode;
  acao?: ReactNode;
}

// Tela/lista vazia que diz o que fazer em vez de so "nenhum item".
export function EmptyState({ icone = "📭", titulo, children, acao }: EmptyStateProps) {
  return (
    <div className="card flex flex-col items-center gap-2 border-dashed px-6 py-10 text-center">
      <span className="text-4xl" aria-hidden="true">
        {icone}
      </span>
      <p className="font-display text-xl font-bold text-slate-800">{titulo}</p>
      {children && <div className="max-w-md text-sm text-slate-500">{children}</div>}
      {acao && <div className="mt-3">{acao}</div>}
    </div>
  );
}
