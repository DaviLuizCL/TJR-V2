import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Tabs } from "./Tabs";

const itens = [
  { valor: "a", rotulo: "Primeira" },
  { valor: "b", rotulo: "Segunda", icone: "🥋" },
];

describe("Tabs", () => {
  it("marca a aba ativa com aria-selected", () => {
    render(<Tabs itens={itens} valor="b" onChange={() => {}} />);

    expect(screen.getByRole("tab", { name: /segunda/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /primeira/i })).toHaveAttribute("aria-selected", "false");
  });

  it("avisa a troca de aba com o valor clicado", async () => {
    const onChange = vi.fn();
    render(<Tabs itens={itens} valor="a" onChange={onChange} />);

    await userEvent.click(screen.getByRole("tab", { name: /segunda/i }));

    expect(onChange).toHaveBeenCalledWith("b");
  });
});
