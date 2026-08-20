import { useEffect } from "react";

import { sincronizar } from "./sync";

export function useSincronizarOutbox(): void {
  useEffect(() => {
    void sincronizar();

    function aoVoltarOnline() {
      void sincronizar();
    }

    window.addEventListener("online", aoVoltarOnline);
    return () => window.removeEventListener("online", aoVoltarOnline);
  }, []);
}
