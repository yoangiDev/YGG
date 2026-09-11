export interface RiotId {
  gameName: string;
  tagLine: string;
}

/**
 * "Hide on bush#KR1" → { gameName: "Hide on bush", tagLine: "KR1" }.
 * Riot admite nombres de 3 a 16 caracteres (con espacios) y tags de 3 a 5; se
 * acepta un tag de 2 por las cuentas antiguas.
 */
export function parseRiotId(value: string): RiotId | null {
  const match = /^\s*([^#]{3,16}?)\s*#\s*([^#\s]{2,5})\s*$/u.exec(value);
  const gameName = match?.[1]?.trim();
  const tagLine = match?.[2];
  if (!gameName || gameName.length < 3 || !tagLine) return null;
  return { gameName, tagLine };
}
