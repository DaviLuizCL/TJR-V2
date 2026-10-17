/**
 * Nome -> pedaco de link legivel ("Resgate de Alto Risco" -> "resgate-de-alto-risco"),
 * pra o link publico ser facil de ditar e mandar no grupo, sem id comprido.
 */
export function slug(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
