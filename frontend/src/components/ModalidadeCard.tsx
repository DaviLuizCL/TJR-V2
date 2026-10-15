import type { ReactNode } from "react";

import { iconeModalidade } from "../lib/modalidade-icone";

interface ModalidadeCardProps {
  nome: string;
  selo?: ReactNode;
  // Acao principal (ex.: link "Pontuar") e secundarias, ja montadas por quem usa.
  acaoPrincipal: ReactNode;
  acoesSecundarias?: ReactNode;
}

export function ModalidadeCard({ nome, selo, acaoPrincipal, acoesSecundarias }: ModalidadeCardProps) {
  return (
    <li className="card group flex flex-col gap-4 p-5 hover:border-neon/50">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-slate-100 text-2xl ring-1 ring-slate-200 group-hover:ring-neon/40"
        >
          {iconeModalidade(nome)}
        </span>
        <div className="min-w-0">
          <p className="font-display text-xl font-bold leading-tight text-slate-900">{nome}</p>
          {selo && <div className="mt-1">{selo}</div>}
        </div>
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-2">
        {acaoPrincipal}
        {acoesSecundarias}
      </div>
    </li>
  );
}
