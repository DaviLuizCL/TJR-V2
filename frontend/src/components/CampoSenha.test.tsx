import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";

import { CampoSenha } from "./CampoSenha";

function Wrapper({ erro, ajuda }: { erro?: string; ajuda?: string }) {
  const { register } = useForm<{ senha: string }>();
  return <CampoSenha id="senha" label="Senha" registro={register("senha")} erro={erro} ajuda={ajuda} />;
}

describe("CampoSenha", () => {
  it("comeca como campo de senha (texto oculto) com botao 'Mostrar'", () => {
    render(<Wrapper />);

    const input = screen.getByLabelText("Senha") as HTMLInputElement;
    expect(input.type).toBe("password");
    expect(screen.getByRole("button", { name: /mostrar/i })).toBeInTheDocument();
  });

  it("clicar em 'Mostrar' revela o texto digitado e o botao vira 'Ocultar'", async () => {
    render(<Wrapper />);

    const input = screen.getByLabelText("Senha") as HTMLInputElement;
    await userEvent.type(input, "minha-senha");
    await userEvent.click(screen.getByRole("button", { name: /mostrar/i }));

    expect(input.type).toBe("text");
    expect(input.value).toBe("minha-senha");
    expect(screen.getByRole("button", { name: /ocultar/i })).toBeInTheDocument();
  });

  it("clicar em 'Ocultar' volta a esconder o texto", async () => {
    render(<Wrapper />);

    await userEvent.click(screen.getByRole("button", { name: /mostrar/i }));
    await userEvent.click(screen.getByRole("button", { name: /ocultar/i }));

    const input = screen.getByLabelText("Senha") as HTMLInputElement;
    expect(input.type).toBe("password");
    expect(screen.getByRole("button", { name: /mostrar/i })).toBeInTheDocument();
  });

  it("mostra mensagem de erro quando informada", () => {
    render(<Wrapper erro="Senha muito curta" />);

    expect(screen.getByText("Senha muito curta")).toBeInTheDocument();
  });

  it("mostra texto de ajuda quando informado", () => {
    render(<Wrapper ajuda="Passe essa senha pessoalmente" />);

    expect(screen.getByText("Passe essa senha pessoalmente")).toBeInTheDocument();
  });
});
