export interface RiotId {
  gameName: string;
  tagLine: string;
}

/**
 * "Hide on bush#KR1" → { gameName: "Hide on bush", tagLine: "KR1" }.
 * Riot allows names of 3 to 16 characters (with spaces) and tags of 3 to 5; a
 * 2-character tag is accepted for old accounts.
 */
export function parseRiotId(value: string): RiotId | null {
  const match = /^\s*([^#]{3,16}?)\s*#\s*([^#\s]{2,5})\s*$/u.exec(value);
  const gameName = match?.[1]?.trim();
  const tagLine = match?.[2];
  if (!gameName || gameName.length < 3 || !tagLine) return null;
  return { gameName, tagLine };
}
