import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "../lib/auth-store";
import { ProtectedRoute } from "./ProtectedRoute";

function renderComRota(caminho: string, papeisPermitidos?: string[]) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <Routes>
        <Route path="/login" element={<div>TELA DE LOGIN</div>} />
        <Route path="/eventos" element={<div>TELA DE EVENTOS</div>} />
        <Route
          path="/protegida"
          element={
            <ProtectedRoute papeisPermitidos={papeisPermitidos}>
              <div>CONTEUDO PROTEGIDO</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, refreshToken: null, usuario: null });
});

describe("ProtectedRoute", () => {
  it("sem token, manda pro login", () => {
    renderComRota("/protegida");

    expect(screen.getByText("TELA DE LOGIN")).toBeInTheDocument();
  });

  it("com token e sem restricao de papel, mostra o conteudo pra qualquer papel", () => {
    useAuthStore.setState({
      accessToken: "tok",
      refreshToken: "tok",
      usuario: { id: "u1", nome: "Arbitro", email: "arb@tjr.app", papel: "ARBITRO" },
    });

    renderComRota("/protegida");

    expect(screen.getByText("CONTEUDO PROTEGIDO")).toBeInTheDocument();
  });

  it("com papeisPermitidos e o papel do usuario nao esta na lista, manda pra /eventos", () => {
    useAuthStore.setState({
      accessToken: "tok",
      refreshToken: "tok",
      usuario: { id: "u1", nome: "Arbitro", email: "arb@tjr.app", papel: "ARBITRO" },
    });

    renderComRota("/protegida", ["COORDENADOR"]);

    expect(screen.getByText("TELA DE EVENTOS")).toBeInTheDocument();
    expect(screen.queryByText("CONTEUDO PROTEGIDO")).not.toBeInTheDocument();
  });

  it("com papeisPermitidos e o papel do usuario esta na lista, mostra o conteudo", () => {
    useAuthStore.setState({
      accessToken: "tok",
      refreshToken: "tok",
      usuario: { id: "u1", nome: "Coordenador", email: "coord@tjr.app", papel: "COORDENADOR" },
    });

    renderComRota("/protegida", ["COORDENADOR"]);

    expect(screen.getByText("CONTEUDO PROTEGIDO")).toBeInTheDocument();
  });
});
