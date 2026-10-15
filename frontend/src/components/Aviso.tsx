import type { ReactNode } from "react";

import { type TipoAviso, useAvisosStore } from "../lib/avisos";

// Nome completo da classe escrito aqui de proposito: o Tailwind so gera no CSS
// classe que ele acha por extenso no codigo (`aviso-${tipo}` seria descartada).
const CLASSE: Record<TipoAviso, string> = {
  sucesso: "aviso-sucesso",
  erro: "aviso-erro",
  alerta: "aviso-alerta",
  info: "aviso-info",
};

const ICONE: Record<TipoAviso, string> = {
  sucesso: "✓",
  erro: "✕",
  alerta: "⚠",
  info: "ℹ",
};

// Mesma linguagem pra todo aviso do sistema: fundo translucido na cor do tipo
// (classes .aviso-* em index.css) + icone. Erro interrompe o leitor de tela
// (role=alert); o resto e status.
export function Aviso({
  tipo,
  children,
  className = "",
}: {
  tipo: TipoAviso;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div role={tipo === "erro" ? "alert" : "status"} className={`aviso ${CLASSE[tipo]} ${className}`}>
      <span aria-hidden="true" className="aviso-icone">
        {ICONE[tipo]}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

// Toasts disparados por avisar(). Fica no topo, abaixo do cabecalho, pra nao
// brigar com a barra fixa de nota no rodape da ficha.
export function AvisosFlutuantes() {
  const avisos = useAvisosStore((state) => state.avisos);
  const fechar = useAvisosStore((state) => state.fechar);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-16 z-50 flex flex-col items-center gap-2 px-4">
      {avisos.map((aviso) => (
        <div
          key={aviso.id}
          role={aviso.tipo === "erro" ? "alert" : "status"}
          className={`aviso ${CLASSE[aviso.tipo]} aviso-flutuante pointer-events-auto w-full max-w-md`}
        >
          <span aria-hidden="true" className="aviso-icone">
            {ICONE[aviso.tipo]}
          </span>
          <p className="min-w-0 flex-1 font-semibold">{aviso.mensagem}</p>
          <button
            type="button"
            aria-label="Fechar aviso"
            onClick={() => fechar(aviso.id)}
            className="-my-1 -mr-1 grid h-8 w-8 shrink-0 place-items-center rounded-lg opacity-70 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
