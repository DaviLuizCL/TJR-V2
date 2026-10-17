import { Link } from "react-router-dom";

// Porta de entrada do site: o publico (professor, torcida) vai pro cronograma
// sem senha; a equipe do evento (juiz, coordenacao) entra pelo login.
export function InicioPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="mb-8 text-center">
        <p className="text-6xl" aria-hidden="true">
          🤖
        </p>
        <p className="mt-2 bg-gradient-to-r from-neon to-plasma bg-clip-text font-display text-6xl font-bold tracking-[0.3em] text-transparent">
          TJR
        </p>
        <p className="eyebrow mt-1 text-slate-500">Torneio Juvenil de Robótica</p>
      </div>

      <div className="card flex w-full max-w-sm flex-col gap-3 border-neon/30 p-6 shadow-glow">
        <Link to="/sequencia" className="btn-primary min-h-16 flex-col gap-0 text-lg">
          <span>📋 Cronograma</span>
          <span className="text-xs font-normal normal-case tracking-normal opacity-80">
            Quem já competiu e quem é a próxima
          </span>
        </Link>
        <Link to="/login" className="btn-secondary min-h-16 flex-col gap-0 text-lg">
          <span>🔑 Entrar</span>
          <span className="text-xs font-normal normal-case tracking-normal text-slate-500">
            Juízes e coordenação
          </span>
        </Link>
      </div>
    </main>
  );
}
