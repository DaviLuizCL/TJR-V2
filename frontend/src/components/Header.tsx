import { Link, useNavigate } from "react-router-dom";

import { useAuthStore } from "../lib/auth-store";
import { useEventoStore } from "../lib/evento-store";

export function Header() {
  const eventoAtualId = useEventoStore((state) => state.eventoAtualId);
  const papel = useAuthStore((state) => state.usuario?.papel);
  const sair = useAuthStore((state) => state.sair);
  const navigate = useNavigate();

  function sairDaConta() {
    sair();
    navigate("/login");
  }
  // Arbitro so precisa chegar em Pontuar (dentro de Individual/Combates, que
  // ja abrem na aba Pontuar por padrao) - o resto e ferramenta de
  // coordenacao/secretaria que ele nao usa e so teria acesso negado (403) se
  // clicasse.
  const ehArbitro = papel === "ARBITRO";
  const ehCoordenador = papel === "COORDENADOR";

  const linkModalidades = eventoAtualId ? `/eventos/${eventoAtualId}/modalidades` : "/eventos";
  const linkFichas = eventoAtualId ? `/eventos/${eventoAtualId}/fichas` : "/eventos";
  const linkCompeticoes = eventoAtualId ? `/eventos/${eventoAtualId}/competicoes` : "/eventos";
  const linkPainel = eventoAtualId ? `/eventos/${eventoAtualId}/painel` : "/eventos";

  return (
    <header className="border-b border-slate-200 bg-white px-6 py-3">
      <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2">
        <span className="text-sm font-semibold uppercase tracking-wide text-slate-400">TJR</span>
        <Link to="/eventos" className="text-sm font-medium text-slate-700 hover:text-slate-900">
          Eventos
        </Link>
        {!ehArbitro && (
          <Link to="/equipes" className="text-sm font-medium text-slate-700 hover:text-slate-900">
            Equipes
          </Link>
        )}
        {!ehArbitro && (
          <Link
            to={linkModalidades}
            className="text-sm font-medium text-slate-700 hover:text-slate-900"
          >
            Modalidades
          </Link>
        )}
        {!ehArbitro && (
          <Link
            to={linkFichas}
            className="text-sm font-medium text-slate-700 hover:text-slate-900"
          >
            Fichas
          </Link>
        )}
        <Link
          to={linkCompeticoes}
          className="text-sm font-medium text-slate-700 hover:text-slate-900"
        >
          Competições
        </Link>
        {!ehArbitro && (
          <Link
            to={linkPainel}
            className="text-sm font-medium text-slate-700 hover:text-slate-900"
          >
            Painel
          </Link>
        )}
        {ehCoordenador && (
          <Link to="/usuarios" className="text-sm font-medium text-slate-700 hover:text-slate-900">
            Staff
          </Link>
        )}
        <button
          type="button"
          onClick={sairDaConta}
          className="ml-auto text-sm font-medium text-slate-700 hover:text-slate-900"
        >
          Sair
        </button>
      </nav>
    </header>
  );
}
