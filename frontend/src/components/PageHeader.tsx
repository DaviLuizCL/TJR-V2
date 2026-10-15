import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface PageHeaderProps {
  titulo: ReactNode;
  // Linha pequena em neon acima do titulo (ex.: "Individual", "Administracao").
  sobretitulo?: string;
  descricao?: ReactNode;
  voltar?: { para: string; rotulo: string };
  acoes?: ReactNode;
}

export function PageHeader({ titulo, sobretitulo, descricao, voltar, acoes }: PageHeaderProps) {
  return (
    <div className="mb-6">
      {voltar && (
        <Link
          to={voltar.para}
          className="mb-3 inline-flex min-h-10 items-center gap-1 text-sm font-medium text-slate-500 hover:text-neon"
        >
          ← {voltar.rotulo}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          {sobretitulo && <p className="eyebrow mb-1">{sobretitulo}</p>}
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">{titulo}</h1>
          {descricao && <p className="mt-2 max-w-2xl text-sm text-slate-500">{descricao}</p>}
        </div>
        {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
      </div>
    </div>
  );
}
