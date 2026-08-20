import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { sincronizar } from "./sync";
import { useSincronizarOutbox } from "./use-sincronizar-outbox";

vi.mock("./sync", () => ({ sincronizar: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useSincronizarOutbox", () => {
  it("dispara sincronizar() ao montar, mesmo sem o evento online", () => {
    renderHook(() => useSincronizarOutbox());

    expect(sincronizar).toHaveBeenCalledTimes(1);
  });

  it("dispara sincronizar() de novo quando o evento online da janela dispara", () => {
    renderHook(() => useSincronizarOutbox());
    expect(sincronizar).toHaveBeenCalledTimes(1);

    window.dispatchEvent(new Event("online"));

    expect(sincronizar).toHaveBeenCalledTimes(2);
  });
});
