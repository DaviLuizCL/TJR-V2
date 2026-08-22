/**
 * `crypto.randomUUID()` só existe em contexto seguro (HTTPS ou localhost) —
 * no ginásio, o árbitro acessa por IP puro em HTTP (ver README, seção de
 * produção), onde essa função simplesmente não existe no navegador e a
 * chamada quebra o lançamento inteiro. `crypto.getRandomValues()`, ao
 * contrário, nunca teve essa restrição (é anterior à exigência de contexto
 * seguro e continua disponível em qualquer origem) — usada aqui pra montar
 * um UUID v4 na mão, sem depender de HTTPS.
 */
export function randomUUID(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
