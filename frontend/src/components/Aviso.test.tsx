import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { avisar, useAvisosStore } from "../lib/avisos";
import { Aviso, AvisosFlutuantes } from "./Aviso";

describe("Aviso", () => {
  it("erro e anunciado como alerta pro leitor de tela", () => {
    render(<Aviso tipo="erro">Deu ruim</Aviso>);

    expect(screen.getByRole("alert")).toHaveTextContent("Deu ruim");
  });

  it("sucesso, alerta e info sao anunciados como status (sem interromper)", () => {
    render(
      <>
        <Aviso tipo="sucesso">A</Aviso>
        <Aviso tipo="alerta">B</Aviso>
        <Aviso tipo="info">C</Aviso>
      </>,
    );

    expect(screen.getAllByRole("status")).toHaveLength(3);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("AvisosFlutuantes", () => {
  beforeEach(() => useAvisosStore.setState({ avisos: [] }));

  it("mostra o aviso disparado de qualquer lugar e deixa fechar", async () => {
    render(<AvisosFlutuantes />);

    act(() => avisar("sucesso", "Pontuação enviada!"));
    expect(screen.getByText("Pontuação enviada!")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /fechar aviso/i }));
    expect(screen.queryByText("Pontuação enviada!")).not.toBeInTheDocument();
  });
});
