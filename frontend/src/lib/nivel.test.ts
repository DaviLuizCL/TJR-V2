import { describe, expect, it } from "vitest";

import { rotuloNivel } from "./nivel";

describe("rotuloNivel", () => {
  it("nivel 1 mostra ABSOLUTO", () => {
    expect(rotuloNivel(1)).toBe("ABSOLUTO");
  });

  it("niveis 2, 3 e 4 mostram Nível N", () => {
    expect(rotuloNivel(2)).toBe("Nível 2");
    expect(rotuloNivel(3)).toBe("Nível 3");
    expect(rotuloNivel(4)).toBe("Nível 4");
  });
});
