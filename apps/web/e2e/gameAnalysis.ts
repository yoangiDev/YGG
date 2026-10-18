/**
 * Synthetic data of a finished match analysis (`GET /games/analyses/{match_id}`), with the shape of
 * `PremiumData` and `Review` (src/features/snapshots/premiumData.ts; the types are not imported because the e2e
 * tsconfig does not resolve the `src` aliases). None of the data comes from a real match: it serves the e2e tests and the
 * screenshots.
 */
type Tone = "bad" | "good" | "neutral";

interface Extra {
  gold?: number;
  dead_for?: number;
  wp_before?: number;
  wp_after?: number;
  killer?: string;
  objective?: string;
}

export const GAME_ANALYSIS_ID = "EUW1_7000000001";
const DURATION = 1900;

const clock = (t: number) => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;

function moment(
  id: number,
  t: number,
  kind: string,
  tone: Tone,
  severity: 1 | 2 | 3,
  title: string,
  text: string,
  place: { x: number; z: number; where: string },
  extra: Extra = {},
) {
  return { id, t, clock: clock(t), kind, tone, severity, title, text, ...place, ...extra };
}

const moments = [
  moment(1, 77, "ward", "good", 1, "Level-1 ward in the lane bush", "You warded the tribush at 1:17. Nobody got a free gank on your lane for the first four minutes.", { x: 11900, z: 3300, where: "Bot lane bush" }),
  moment(2, 226, "death", "bad", 2, "Died to Qiyana without seeing her", "Qiyana had been out of sight for 38 s and came out of the river bush. You still had a summoner spell up.", { x: 12300, z: 2100, where: "Bot lane" }, { gold: -310, dead_for: 20, wp_before: 51, wp_after: 47, killer: "Qiyana" }),
  moment(3, 410, "back", "good", 1, "Recall on a pushed wave", "Your wave was crashing into their tower, so the recall cost no farm and you came back with a full item.", { x: 13100, z: 1500, where: "Bot lane" }),
  moment(4, 614, "fog", "bad", 2, "Gragas out of sight for 44 s", "Nobody on your team had seen Gragas for 44 s. He came out of the fog 7 s before the 2v1.", { x: 10400, z: 4200, where: "River, bot side" }),
  moment(5, 715, "death", "bad", 3, "Died 2v1 to Gragas and Qiyana", "The same mistake as at 3:46: you stayed after the wave was pushed. 320 gold given and 25 s dead while they took the top outer turret.", { x: 10800, z: 3600, where: "Bot lane, near the river" }, { gold: -320, dead_for: 25, wp_before: 52, wp_after: 41, killer: "Gragas" }),
  moment(6, 1030, "objective", "bad", 2, "Dragon lost: your team arrived without you", "You were two waves away when the fight started at the pit. Your team lost 2 for 3 and the dragon.", { x: 9800, z: 4400, where: "Dragon pit" }, { objective: "Dragon", wp_before: 46, wp_after: 38 }),
  moment(7, 1150, "flash", "bad", 2, "Flash spent 23 s before the next dragon", "Flash takes 300 s to come back. You reached the pit without it and died first.", { x: 9300, z: 4600, where: "River, dragon side" }),
  moment(8, 1490, "fight", "bad", 3, "Teamfight in mid lost 2 for 5", "You opened the fight from the wrong side of the wall and your support was not in range.", { x: 7600, z: 7300, where: "Mid lane" }, { gold: -980, wp_before: 38, wp_after: 19 }),
  moment(9, 1745, "swing", "bad", 3, "Baron thrown with the team behind", "Starting Baron at 6,245 gold behind and no vision of the pit gave them the pick and the game.", { x: 5200, z: 10100, where: "Baron pit" }, { objective: "Baron", wp_before: 31, wp_after: 9 }),
];

/** Their team's WP every 10 s: a small lead at the start and a drop in steps at the bad moments. */
const wp: [number, number][] = Array.from({ length: Math.floor((DURATION - 90) / 10) + 1 }, (_, i) => {
  const t = 90 + i * 10;
  const base = 0.5 + 0.03 * Math.min(t, 600) / 600 - 0.3 * Math.max(0, t - 600) / (DURATION - 600);
  const drops = moments.filter((m) => m.tone === "bad" && m.wp_before !== undefined && m.wp_after !== undefined && t >= m.t)
    .reduce((sum, m) => sum + ((m.wp_after as number) - (m.wp_before as number)) / 100 * 0.4, 0);
  return [t, Math.max(0.02, Math.min(0.97, base + drops))];
});

const player = (champion: string, role: string, side: "ally" | "enemy", kda: [number, number, number], cs: number, gold: number, you = false) => ({
  champion, role, you, side, kills: kda[0], deaths: kda[1], assists: kda[2], level: 15 + (cs > 200 ? 2 : 0), cs, gold,
  damage: 8000 + cs * 60, taken: 9000 + kda[1] * 1500, vision: 12 + (role === "UTILITY" ? 40 : 6), wards: role === "UTILITY" ? 21 : 6, plates: 1,
});

const game = {
  match_id: GAME_ANALYSIS_ID,
  champion: "Kaisa",
  role: "BOTTOM",
  win: false,
  duration: DURATION,
  played_at: "2026-10-12T19:40:00Z",
  opponent: "Xayah",
  stats: { kills: 6, deaths: 7, assists: 4, flash_suboptimal: 1 },
  flashes: [{ time: 1127, use: "escape", offensive: 0, suboptimal: 1 }],
  wp,
  moments,
  numbers: { gold_diff_10: 1244, gold_diff_14: 1151, wp_15: 0.51, wp_max: 0.53, wp_min: 0.09 },
  scoreboard: {
    players: [
      player("Renekton", "TOP", "ally", [3, 5, 6], 188, 10400),
      player("Viego", "JUNGLE", "ally", [5, 6, 8], 142, 10900),
      player("Ahri", "MIDDLE", "ally", [4, 7, 5], 201, 11200),
      player("Kaisa", "BOTTOM", "ally", [6, 7, 4], 236, 12600, true),
      player("Lulu", "UTILITY", "ally", [0, 8, 14], 41, 7300),
      player("Jax", "TOP", "enemy", [7, 3, 5], 214, 12100),
      player("Gragas", "JUNGLE", "enemy", [6, 3, 12], 151, 11800),
      player("Qiyana", "MIDDLE", "enemy", [9, 4, 7], 207, 13300),
      player("Xayah", "BOTTOM", "enemy", [8, 2, 9], 244, 14100),
      player("Braum", "UTILITY", "enemy", [1, 4, 19], 38, 8200),
    ],
    teams: {
      ally: { kills: 18, deaths: 33, gold: 52400, towers: 3, dragons: 1, barons: 0, heralds: 1, grubs: 3 },
      enemy: { kills: 33, deaths: 18, gold: 59500, towers: 9, dragons: 3, barons: 1, heralds: 1, grubs: 3 },
    },
  },
  rating: {
    total: -48.2,
    score: 31,
    median: -20.5,
    parts: [
      { kind: "death", points: -31.4, good: 0, bad: 2 },
      { kind: "fight", points: -14.8, good: 0, bad: 1 },
      { kind: "swing", points: -9.1, good: 0, bad: 1 },
      { kind: "objective", points: -4.6, good: 0, bad: 1 },
      { kind: "ward", points: 4.2, good: 1, bad: 0 },
      { kind: "back", points: 3.5, good: 1, bad: 0 },
    ],
  },
};

export const gameResult = {
  summary: {
    tier: "EMERALD",
    role: "BOTTOM",
    games: 1,
    wins: 0,
    metrics: {},
    patterns: [
      { kind: "death", title: "Dying without vision", text: "Two of your seven deaths came from enemies you had not seen for 30 s or more.", tone: "bad", weight: 1, moments: [`${GAME_ANALYSIS_ID}:2`, `${GAME_ANALYSIS_ID}:5`] },
    ],
  },
  games: [game],
  missing: {},
};

const key = (id: number) => `${GAME_ANALYSIS_ID}:${id}`;

export const gameReview = {
  headline: "You won your lane and played the waves well. What lost this game was information, not mechanics.",
  coach_summary:
    "Your lane is not why this game was lost. You were 1,244 gold ahead at 10:00 and 1,151 at 14:00, and your team's win chance peaked at 53%.\n\nWhat hurt was what you could not see: two deaths to enemies you had no idea about, a sidelane opening right before a dragon, and a Baron started 6,245 gold behind. Those are the moments you controlled.",
  lessons: [
    {
      title: "Recall as soon as the wave is pushed, and count who you have not seen",
      why: "At 3:46 your wave was already pushing into their tower, which is the moment to recall, and you stayed. Qiyana killed you unseen with a summoner spell up, and at 11:55 Gragas did the same after 44 s in the fog.",
      fix: "After pushing the wave, press recall at once. Before you move forward, count the enemies you have not seen: after 30-40 s, stay near vision or your tower.",
      moments: [key(2), key(4), key(5)],
    },
    {
      title: "Keep Flash for the objective",
      why: "At 19:10 you spent Flash escaping a sidelane, 23 s before the dragon. Flash takes 300 s to come back, so you arrived without it.",
      fix: "From base, go mid with your team. If you take a sidelane, collect one wave and go, and do not spend Flash when the next objective is under a minute away.",
      moments: [key(7), key(6)],
    },
  ],
  strengths: [
    { title: "Wave management in the laning phase", detail: "A slow push at 2:35, a recall on a pushed wave at 6:50 and a lane lead that held until 14:00.", moments: [key(3)] },
    { title: "Vision at the start", detail: "A level-1 ward in the lane bush gave you four quiet minutes.", moments: [key(1)] },
  ],
  game_notes: [],
  moment_notes: [],
  next_game: [
    "When your wave is pushed into their tower, recall straight away.",
    "After 30-40 s without sight of an enemy, play near vision or your tower.",
    "Open mid from base, and keep Flash for the next objective.",
  ],
};

export const gameAnalysisResponse = {
  match_id: GAME_ANALYSIS_ID,
  status: "done",
  error: null,
  created_at: "2026-10-12T20:30:00Z",
  result: gameResult,
  review: gameReview,
};
