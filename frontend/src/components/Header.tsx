import { Link } from "react-router-dom";

import { useEventoStore } from "../lib/evento-store";

export function Header() {
  const eventoAtualId = useEventoStore((state) => state.eventoAtualId);

  const linkModalidades = eventoAtualId ? `/eventos/${eventoAtualId}/modalidades` : "/eventos";
  const linkFichas = eventoAtualId ? `/eventos/${eventoAtualId}/fichas` : "/eventos";
  const linkIndividual = eventoAtualId ? `/eventos/${eventoAtualId}/individual` : "/eventos";
  const linkPainel = eventoAtualId ? `/eventos/${eventoAtualId}/painel` : "/eventos";
  const linkCombates = eventoAtualId ? `/eventos/${eventoAtualId}/combates` : "/eventos";

  return (
    <header className="border-b border-slate-200 bg-white px-6 py-3">
      <nav className="mx-auto flex max-w-5xl items-center gap-6">
        <span className="text-sm font-semibold uppercase tracking-wide text-slate-400">TJR</span>
        <Link to="/eventos" className="text-sm font-medium text-slate-700 hover:text-slate-900">
          Eventos
        </Link>
        <Link to="/equipes" className="text-sm font-medium text-slate-700 hover:text-slate-900">
          Equipes
        </Link>
        <Link
          to={linkModalidades}
          className="text-sm font-medium text-slate-700 hover:text-slate-900"
        >
          Modalidades
        </Link>
        <Link to={linkFichas} className="text-sm font-medium text-slate-700 hover:text-slate-900">
          Fichas
        </Link>
        <Link
          to={linkIndividual}
          className="text-sm font-medium text-slate-700 hover:text-slate-900"
        >
          Individual
        </Link>
        <Link
          to={linkCombates}
          className="text-sm font-medium text-slate-700 hover:text-slate-900"
        >
          Combates
        </Link>
        <Link
          to={linkPainel}
          className="text-sm font-medium text-slate-700 hover:text-slate-900"
        >
          Painel
        </Link>
      </nav>
    </header>
  );
}
