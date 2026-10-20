import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { InicioPage } from "./InicioPage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<InicioPage />} />
        <Route path="/sequencia" element={<p>pagina da sequencia</p>} />
        <Route path="/equipes-inscritas" element={<p>pagina das equipes</p>} />
        <Route path="/regras" element={<p>pagina das regras</p>} />
        <Route path="/login" element={<p>pagina de login</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("InicioPage", () => {
  it("mostra so as quatro opcoes: Cronograma, Equipes inscritas, Regras e Entrar", () => {
    renderPage();

    expect(screen.getAllByRole("link")).toHaveLength(4);
    expect(screen.getByRole("link", { name: /regras/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /cronograma/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /equipes inscritas/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /entrar/i })).toBeInTheDocument();
  });

  it("Cronograma leva pra sequencia de competicao", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("link", { name: /cronograma/i }));

    expect(screen.getByText("pagina da sequencia")).toBeInTheDocument();
  });

  it("Equipes inscritas leva pra lista publica de equipes", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("link", { name: /equipes inscritas/i }));

    expect(screen.getByText("pagina das equipes")).toBeInTheDocument();
  });

  it("Regras leva pros PDFs de regras das modalidades", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("link", { name: /regras/i }));

    expect(screen.getByText("pagina das regras")).toBeInTheDocument();
  });

  it("Entrar leva pro login", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("link", { name: /entrar/i }));

    expect(screen.getByText("pagina de login")).toBeInTheDocument();
  });
});
