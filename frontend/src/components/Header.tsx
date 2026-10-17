import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuthStore } from "../lib/auth-store";
import { useEventoStore } from "../lib/evento-store";

const ROTULO_PAPEL: Record<string, string> = {
  COORDENADOR: "Coordenação",
  ARBITRO: "Juiz",
  SECRETARIA: "Secretaria",
};

function classesLink({ isActive }: { isActive: boolean }) {
  return `inline-flex min-h-10 items-center gap-1.5 rounded-lg px-3 font-display text-[15px] font-bold uppercase tracking-wider ${
    isActive
      ? "bg-neon/10 text-neon ring-1 ring-neon/40"
      : "text-slate-600 hover:bg-slate-200/60 hover:text-slate-900"
  }`;
}

export function Header() {
  const eventoGuardado = useEventoStore((state) => state.eventoAtualId);
  const usuario = useAuthStore((state) => state.usuario);
  const papel = usuario?.papel;
  const sair = useAuthStore((state) => state.sair);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  // Primeiro acesso por um link direto (ex.: /eventos/:id/admin/checklist) ainda
  // nao guardou o evento: le do endereco, senao todo link cai em /eventos.
  const eventoAtualId = eventoGuardado ?? pathname.match(/^\/eventos\/([^/]+)/)?.[1] ?? null;
  // Pontuar/rodadas/sequencia moram debaixo de /modalidades/:id na URL, mas pro
  // usuario fazem parte de Competicoes - acende o link certo.
  const emCompeticao = /\/(competicoes|pontuar|rodadas|ordem|lancamentos|partidas)/.test(pathname);

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
  const linkCompeticoes = eventoAtualId ? `/eventos/${eventoAtualId}/competicoes` : "/eventos";
  const linkPainel = eventoAtualId ? `/eventos/${eventoAtualId}/painel` : "/eventos";
  const linkAdmin = eventoAtualId ? `/eventos/${eventoAtualId}/admin` : "/eventos";

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-slate-50/85 backdrop-blur">
      <div className="h-0.5 bg-gradient-to-r from-neon via-plasma to-neon" aria-hidden="true" />
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-1 gap-y-2 px-4 py-2 sm:px-6">
        <Link
          to={linkCompeticoes}
          aria-label="Início"
          className="mr-3 flex items-center gap-2 font-display text-2xl font-bold tracking-widest"
        >
          <span aria-hidden="true" className="text-xl">
            🤖
          </span>
          <span className="bg-gradient-to-r from-neon to-plasma bg-clip-text text-transparent">
            TJR
          </span>
        </Link>
        <NavLink
          to={linkCompeticoes}
          className={({ isActive }) => classesLink({ isActive: isActive || emCompeticao })}
        >
          <span aria-hidden="true">🏁</span>Competições
        </NavLink>
        {!ehArbitro && (
          <NavLink to="/equipes" className={classesLink}>
            Equipes
          </NavLink>
        )}
        {!ehArbitro && (
          <NavLink
            to={linkModalidades}
            className={({ isActive }) => classesLink({ isActive: isActive && !emCompeticao })}
          >
            Modalidades
          </NavLink>
        )}
        {!ehArbitro && (
          <NavLink to={linkPainel} className={classesLink}>
            Painel
          </NavLink>
        )}
        {ehCoordenador && (
          <NavLink to={linkAdmin} className={classesLink}>
            <span aria-hidden="true">⚙️</span>Administração
          </NavLink>
        )}
        <div className="ml-auto flex items-center gap-3">
          {usuario?.nome && (
            <span className="hidden text-right text-xs leading-tight text-slate-500 sm:block">
              <span className="block font-semibold text-slate-700">{usuario.nome}</span>
              {ROTULO_PAPEL[papel ?? ""] ?? papel}
            </span>
          )}
          <button
            type="button"
            onClick={sairDaConta}
            className="min-h-10 rounded-lg border border-slate-300 px-3 text-sm font-semibold text-slate-600 hover:border-red-400 hover:text-red-700"
          >
            Sair
          </button>
        </div>
      </nav>
    </header>
  );
}
