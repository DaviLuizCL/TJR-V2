import { Link, useParams } from "react-router-dom";

export function VoltarAdmin() {
  const { eventoId } = useParams<{ eventoId: string }>();
  return (
    <Link
      to={`/eventos/${eventoId}/admin`}
      className="mb-4 inline-block text-sm font-medium text-slate-600 underline"
    >
      ← Voltar para Administração
    </Link>
  );
}
