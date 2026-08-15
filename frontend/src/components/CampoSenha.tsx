import { useState } from "react";
import type { UseFormRegisterReturn } from "react-hook-form";

export function CampoSenha({
  id,
  label,
  registro,
  erro,
  ajuda,
}: {
  id: string;
  label: string;
  registro: UseFormRegisterReturn;
  erro?: string;
  ajuda?: string;
}) {
  const [visivel, setVisivel] = useState(false);

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visivel ? "text" : "password"}
          className="w-full rounded border border-slate-300 px-3 py-2 pr-20"
          {...registro}
        />
        <button
          type="button"
          onClick={() => setVisivel((atual) => !atual)}
          className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-600 hover:text-slate-900"
        >
          {visivel ? "Ocultar" : "Mostrar"}
        </button>
      </div>
      {erro && <p className="mt-1 text-sm text-red-600">{erro}</p>}
      {ajuda && <p className="mt-1 text-xs text-slate-500">{ajuda}</p>}
    </div>
  );
}
