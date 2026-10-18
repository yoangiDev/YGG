/**
 * The history in one-day sessions, as on DPM, split by build: a snapshot is a stretch of consecutive
 * sessions of a single build (each build has its own table of types, and the API rejects those that cross it).
 */

export interface SessionGame {
  match_id: string;
  creation_time: string;
  game_version: string;
  champion: string;
  win: boolean;
}

export interface Session {
  key: string;
  day: string; // YYYY-MM-DD in local time
  games: SessionGame[];
  wins: number;
}

export interface BuildGroup {
  build: string; // "16.19.823", or "" if the match is from before the version was stored
  patch: string; // "16.19"
  sessions: Session[]; // from the most recent to the oldest
}

/** '16.19.823.722' → '16.19.823': the fourth number is the revision, which doesn't change the format. */
const buildOf = (version: string) => version.split(".").slice(0, 3).join(".");

const localDay = (iso: string) => {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function groupSessions(games: SessionGame[]): BuildGroup[] {
  const sorted = [...games].sort((a, b) => b.creation_time.localeCompare(a.creation_time));
  const groups: BuildGroup[] = [];
  for (const game of sorted) {
    const build = game.game_version ? buildOf(game.game_version) : "";
    let group = groups.at(-1);
    if (group?.build !== build) {
      group = { build, patch: build.split(".").slice(0, 2).join("."), sessions: [] };
      groups.push(group);
    }
    const day = localDay(game.creation_time);
    let session = group.sessions.at(-1);
    if (session?.day !== day) {
      session = { key: `${build}|${day}`, day, games: [], wins: 0 };
      group.sessions.push(session);
    }
    session.games.push(game);
    session.wins += game.win ? 1 : 0;
  }
  return groups;
}

/** A build's label: the patch and, if the list has several of the same patch (a hotfix), which one it is. */
export function buildLabel(group: BuildGroup, groups: BuildGroup[]): string {
  if (!group.build) return "Unknown patch";
  const hotfixes = new Set(groups.filter((g) => g.patch === group.patch).map((g) => g.build)).size > 1;
  return hotfixes ? `Patch ${group.patch} · build ${group.build.split(".")[2]}` : `Patch ${group.patch}`;
}

/** The sessions between two of a single build, both included. */
export function sessionRange(group: BuildGroup, a: string, b: string): Session[] {
  const i = group.sessions.findIndex((s) => s.key === a);
  const j = group.sessions.findIndex((s) => s.key === b);
  if (i < 0 || j < 0) return [];
  return group.sessions.slice(Math.min(i, j), Math.max(i, j) + 1);
}

/** The snapshot's period: from the first to the last match of the sessions, with a minute of margin (between
 * two matches there is at least a quarter of an hour, so the margin doesn't pull in any from outside). */
export function periodOf(sessions: Session[]): { date_from: number; date_to: number } {
  const times = sessions.flatMap((s) => s.games.map((g) => Math.floor(new Date(g.creation_time).getTime() / 1000)));
  return { date_from: Math.min(...times) - 60, date_to: Math.max(...times) + 60 };
}
