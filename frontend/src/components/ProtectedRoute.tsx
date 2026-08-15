import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuthStore } from "../lib/auth-store";

export function ProtectedRoute({
  children,
  papeisPermitidos,
}: {
  children: ReactNode;
  papeisPermitidos?: string[];
}) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const papel = useAuthStore((state) => state.usuario?.papel);

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  if (papeisPermitidos && papel && !papeisPermitidos.includes(papel)) {
    return <Navigate to="/eventos" replace />;
  }

  return <>{children}</>;
}
