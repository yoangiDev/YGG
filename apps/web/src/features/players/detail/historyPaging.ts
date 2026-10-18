/** The history's first page brings 20 matches; each «load more», 10. */
export const FIRST_PAGE = 20;
export const NEXT_PAGE = 10;

export function historyPageLimit(offset: number): number {
  return offset === 0 ? FIRST_PAGE : NEXT_PAGE;
}

/**
 * Offset of the next page, or undefined when Riot returns no more.
 * It advances by the requested size and not the received one: if some match
 * couldn't be downloaded, the page arrives short but the history goes on.
 */
export function nextHistoryOffset(lastPageSize: number, lastOffset: number): number | undefined {
  return lastPageSize === 0 ? undefined : lastOffset + historyPageLimit(lastOffset);
}

/**
 * Joins the pages without repeating matches. If the player finishes a match between
 * one page and the next, Riot's pagination shifts by one position.
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
