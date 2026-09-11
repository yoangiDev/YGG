/** La primera página del historial trae 20 partidas; cada «cargar más», 10. */
export const FIRST_PAGE = 20;
export const NEXT_PAGE = 10;

export function historyPageLimit(offset: number): number {
  return offset === 0 ? FIRST_PAGE : NEXT_PAGE;
}

/**
 * Offset de la siguiente página, o undefined cuando Riot ya no devuelve más.
 * Se avanza por el tamaño pedido y no por el recibido: si alguna partida no se
 * pudo descargar, la página llega corta pero el historial sigue.
 */
export function nextHistoryOffset(lastPageSize: number, lastOffset: number): number | undefined {
  return lastPageSize === 0 ? undefined : lastOffset + historyPageLimit(lastOffset);
}

/**
 * Une las páginas sin repetir partidas. Si el jugador termina una partida entre
 * una página y la siguiente, la paginación de Riot se desplaza una posición.
 */
export function mergeHistoryPages<T extends { match_id: string }>(pages: readonly (readonly T[])[]): T[] {
  const seen = new Set<string>();
  const merged: T[] = [];
  for (const page of pages) {
    for (const match of page) {
      if (seen.has(match.match_id)) continue;
      seen.add(match.match_id);
      merged.push(match);
    }
  }
  return merged;
}
