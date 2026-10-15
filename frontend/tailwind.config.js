/** @type {import('tailwindcss').Config} */

// TEMA ESCURO "ARENA" — paletas INVERTIDAS de proposito.
//
// O front inteiro foi escrito em tema claro (bg-white, text-slate-800, bg-emerald-50 de
// fundo de sucesso, text-red-700 de erro...). Em vez de reescrever as ~50 telas, as
// familias de cor usadas pelo app tem os tons invertidos aqui: o tom 50 virou o fundo
// mais escuro e o 900 o texto mais claro. Resultado: o significado de cada classe
// continua o mesmo ("fundo suave de sucesso", "texto forte de erro"), so que no escuro.
//
//   - `white` = superficie de card/input (escura), nao branco de verdade.
//   - Botao "solido" (bg-slate-800 / bg-emerald-700 / bg-red-600 + text-white) vira
//     cor clara/neon com texto escuro — e o visual pretendido.
//   - Cor nova de marca: `neon` (ciano) e `plasma` (violeta). Use as classes de
//     componente de index.css (btn-primary, card, chip...) antes de cor crua.
//
// Nao use as paletas padrao do Tailwind (gray, blue...) sem inverter aqui tambem.
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        white: "#121a2b",
        slate: {
          50: "#070b14",
          100: "#0e1524",
          200: "#1c2740",
          300: "#2a3754",
          400: "#55627e",
          500: "#8592ad",
          600: "#a4afc6",
          700: "#c4cde0",
          800: "#e1e7f2",
          900: "#f6f8fc",
        },
        emerald: {
          50: "#06231b",
          100: "#0a3428",
          200: "#0f4a37",
          300: "#166b4f",
          400: "#1f9a6f",
          500: "#2fd396",
          600: "#4be3a8",
          700: "#5ef2b6",
          800: "#9df7d2",
          900: "#d4fdec",
        },
        green: {
          50: "#06231b",
          100: "#0a3428",
          200: "#0f4a37",
          300: "#166b4f",
          400: "#1f9a6f",
          500: "#2fd396",
          600: "#4be3a8",
          700: "#5ef2b6",
          800: "#9df7d2",
          900: "#d4fdec",
        },
        red: {
          50: "#2a0b14",
          100: "#3d101d",
          200: "#5c1629",
          300: "#86203a",
          400: "#c22f55",
          500: "#ff4d7a",
          600: "#ff6b8f",
          700: "#ff86a3",
          800: "#ffb3c5",
          900: "#ffe0e8",
        },
        amber: {
          50: "#271a05",
          100: "#3a2707",
          200: "#56390b",
          300: "#7d5310",
          400: "#b97a14",
          500: "#f5a524",
          600: "#ffb94a",
          700: "#ffc768",
          800: "#ffd994",
          900: "#fff0cf",
        },
        neon: {
          DEFAULT: "#22e5ff",
          soft: "#0b3a47",
          dim: "#14a3b8",
        },
        plasma: {
          DEFAULT: "#a66bff",
          soft: "#2a1a4a",
        },
      },
      fontFamily: {
        display: [
          '"Rajdhani"',
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,229,255,.35), 0 0 24px -4px rgba(34,229,255,.45)",
        "glow-plasma": "0 0 0 1px rgba(166,107,255,.35), 0 0 24px -4px rgba(166,107,255,.5)",
        card: "0 1px 0 0 rgba(255,255,255,.04) inset, 0 8px 24px -12px rgba(0,0,0,.7)",
      },
    },
  },
  plugins: [],
};
