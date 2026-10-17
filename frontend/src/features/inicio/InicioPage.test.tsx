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
        <Route path="/login" element={<p>pagina de login</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("InicioPage", () => {
  it("mostra so as duas opcoes: Cronograma e Entrar", () => {
    renderPage();

    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /cronograma/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /entrar/i })).toBeInTheDocument();
  });

  it("Cronograma leva pra sequencia de competicao", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("link", { name: /cronograma/i }));

    expect(screen.getByText("pagina da sequencia")).toBeInTheDocument();
  });

  it("Entrar leva pro login", async () => {
    renderPage();

    await userEvent.click(screen.getByRole("link", { name: /entrar/i }));

    expect(screen.getByText("pagina de login")).toBeInTheDocument();
  });
});
