import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "../lib/auth-store";
import { useEventoStore } from "../lib/evento-store";
import { Header } from "./Header";

function renderHeader() {
  return render(
    <MemoryRouter initialEntries={["/eventos"]}>
      <Routes>
        <Route path="/login" element={<div>TELA DE LOGIN</div>} />
        <Route path="*" element={<Header />} />
      </Routes>
    </MemoryRouter>,
  );
}

function logarComo(papel: string) {
  useAuthStore.setState({
    accessToken: "tok",
    refreshToken: "tok",
    usuario: { id: "u1", nome: "Usuario Teste", email: "user@tjr.app", papel },
  });
}

beforeEach(() => {
  useEventoStore.setState({ eventoAtualId: null });
  logarComo("COORDENADOR");
});

describe("Header", () => {
  it("linka equipes e eventos sempre nos mesmos locais", () => {
    renderHeader();

    expect(screen.getByRole("link", { name: /equipes/i })).toHaveAttribute("href", "/equipes");
    expect(screen.getByRole("link", { name: /eventos/i })).toHaveAttribute("href", "/eventos");
  });

  it("sem evento atual, manda modalidades/fichas/competicoes/painel para o seletor de eventos", () => {
    renderHeader();

    expect(screen.getByRole("link", { name: /modalidades/i })).toHaveAttribute("href", "/eventos");
    expect(screen.getByRole("link", { name: /^fichas$/i })).toHaveAttribute("href", "/eventos");
    expect(screen.getByRole("link", { name: /competi[cç][oõ]es/i })).toHaveAttribute(
      "href",
      "/eventos",
    );
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
    expect(screen.getByRole("link", { name: /competi[cç][oõ]es/i })).toHaveAttribute(
      "href",
      "/eventos/evt-9/competicoes",
    );
    expect(screen.getByRole("link", { name: /painel/i })).toHaveAttribute(
      "href",
      "/eventos/evt-9/painel",
    );
  });

  it("nao mostra mais os links soltos de Rodadas, Horarios, Pontuar, Chaveamento, Individual e Combates (viraram abas dentro de Competicoes)", () => {
    useEventoStore.setState({ eventoAtualId: "evt-9" });

    renderHeader();

    expect(screen.queryByRole("link", { name: /^rodadas$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^hor[aá]rios$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^pontuar$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^chaveamento$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^individual$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^combates$/i })).not.toBeInTheDocument();
  });

  it("arbitro so ve Eventos e Competicoes - sem acesso as ferramentas de coordenacao", () => {
    logarComo("ARBITRO");

    renderHeader();

    expect(screen.getByRole("link", { name: /eventos/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /competi[cç][oõ]es/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /equipes/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^modalidades$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^fichas$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /painel/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /staff/i })).not.toBeInTheDocument();
  });

  it("secretaria mantem acesso amplo de leitura, igual coordenador, mas sem Staff", () => {
    logarComo("SECRETARIA");

    renderHeader();

    expect(screen.getByRole("link", { name: /equipes/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^modalidades$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /painel/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /staff/i })).not.toBeInTheDocument();
  });

  it("coordenador ve o link Staff pra cadastrar arbitro/secretaria", () => {
    logarComo("COORDENADOR");

    renderHeader();

    expect(screen.getByRole("link", { name: /staff/i })).toHaveAttribute("href", "/usuarios");
  });

  it("mostra o botao Sair pra qualquer papel logado", () => {
    logarComo("ARBITRO");

    renderHeader();

    expect(screen.getByRole("button", { name: /sair/i })).toBeInTheDocument();
  });

  it("BUG-06: a navegacao quebra linha em vez de forcar rolagem horizontal em telas estreitas", () => {
    // jsdom nao calcula layout real (nao ha como medir overflow de verdade
    // aqui - ver verificacao manual descrita no plano), entao o teste
    // possivel e estrutural: garante que a classe que permite quebra de
    // linha esta presente e nao foi removida por engano numa mudanca futura.
    renderHeader();

    const nav = screen.getByRole("link", { name: /eventos/i }).closest("nav")!;
    expect(nav.className).toMatch(/flex-wrap/);
  });

  it("clicar em Sair limpa a sessao e manda pro login", async () => {
    logarComo("COORDENADOR");

    renderHeader();
    await userEvent.click(screen.getByRole("button", { name: /sair/i }));

    expect(await screen.findByText("TELA DE LOGIN")).toBeInTheDocument();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().usuario).toBeNull();
  });
});
