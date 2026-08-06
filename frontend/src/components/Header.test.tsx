import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { useEventoStore } from "../lib/evento-store";
import { Header } from "./Header";

function renderHeader() {
  return render(
    <MemoryRouter>
      <Header />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useEventoStore.setState({ eventoAtualId: null });
});

describe("Header", () => {
  it("linka equipes e eventos sempre nos mesmos locais", () => {
    renderHeader();

    expect(screen.getByRole("link", { name: /equipes/i })).toHaveAttribute("href", "/equipes");
    expect(screen.getByRole("link", { name: /eventos/i })).toHaveAttribute("href", "/eventos");
  });

  it("sem evento atual, manda modalidades/fichas/individual/combates/painel para o seletor de eventos", () => {
    renderHeader();

    expect(screen.getByRole("link", { name: /modalidades/i })).toHaveAttribute("href", "/eventos");
    expect(screen.getByRole("link", { name: /^fichas$/i })).toHaveAttribute("href", "/eventos");
    expect(screen.getByRole("link", { name: /^individual$/i })).toHaveAttribute("href", "/eventos");
    expect(screen.getByRole("link", { name: /^combates$/i })).toHaveAttribute("href", "/eventos");
    expect(screen.getByRole("link", { name: /painel/i })).toHaveAttribute("href", "/eventos");
  });

  it("com evento atual definido, linka direto para os hubs daquele evento", () => {
    useEventoStore.setState({ eventoAtualId: "evt-9" });

    renderHeader();

    expect(screen.getByRole("link", { name: /modalidades/i })).toHaveAttribute(
      "href",
      "/eventos/evt-9/modalidades",
    );
    expect(screen.getByRole("link", { name: /^fichas$/i })).toHaveAttribute(
      "href",
      "/eventos/evt-9/fichas",
    );
    expect(screen.getByRole("link", { name: /^individual$/i })).toHaveAttribute(
      "href",
      "/eventos/evt-9/individual",
    );
    expect(screen.getByRole("link", { name: /^combates$/i })).toHaveAttribute(
      "href",
      "/eventos/evt-9/combates",
    );
    expect(screen.getByRole("link", { name: /painel/i })).toHaveAttribute(
      "href",
      "/eventos/evt-9/painel",
    );
  });

  it("nao mostra mais os links soltos de Rodadas, Horarios, Pontuar e Chaveamento (viraram abas dentro de Individual/Combates)", () => {
    useEventoStore.setState({ eventoAtualId: "evt-9" });

    renderHeader();

    expect(screen.queryByRole("link", { name: /^rodadas$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^hor[aá]rios$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^pontuar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^chaveamento$/i })).not.toBeInTheDocument();
  });
});
