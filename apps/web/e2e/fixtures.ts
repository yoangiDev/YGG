/**
 * Datos de demostración para las pruebas e2e y las capturas de pantalla.
 * Son deterministas (sin Math.random) para que las capturas no cambien entre ejecuciones.
 */

const MAP_UNITS = 14870;

export const adminUser = { id: 1, email: "coach@ygg.gg", username: "coach", role: "admin", is_active: true, avatar_url: null };
export const user = { ...adminUser, role: "user" };

export const token = { access_token: "e2e-access-token", token_type: "bearer", expires_in: 900 };

export const players = [
  { id: 1, game_name: "Faker", tag_line: "KR1", region: "KR", tier: "MASTER", rank: "I", lp: 412, wins: 118, losses: 94, role: "MID", nickname: "Main account", profile_icon_id: 6 },
  { id: 2, game_name: "Caps", tag_line: "EUW", region: "EUW", tier: "GRANDMASTER", rank: "I", lp: 731, wins: 201, losses: 170, role: "MID", nickname: "", profile_icon_id: 7 },
  { id: 3, game_name: "Bot Lane Diff", tag_line: "0001", region: "EUW", tier: "DIAMOND", rank: "II", lp: 64, wins: 87, losses: 90, role: "BOTTOM", nickname: "Scrim ADC", profile_icon_id: 9 },
  { id: 4, game_name: "Gank Plank", tag_line: "JGL", region: "NA", tier: "EMERALD", rank: "IV", lp: 12, wins: 45, losses: 52, role: "JUNGLE", nickname: "", profile_icon_id: 11 },
  { id: 5, game_name: "Warded", tag_line: "SUP", region: "EUNE", tier: "", rank: "", lp: 0, wins: 0, losses: 0, role: "SUPPORT", nickname: "New signing", profile_icon_id: 0 },
].map((p) => ({ ...p, puuid: `puuid-${p.id}`, notes: "", win_rate: p.wins + p.losses ? Math.round((p.wins / (p.wins + p.losses)) * 1000) / 10 : 0 }));

export const [player] = players;

export const snapshots = [
  { id: 42, player_id: 1, date_from: "2026-08-12T00:00:00Z", date_to: "2026-09-11T00:00:00Z", description: "After bootcamp", notes: "", match_count: 24 },
  { id: 41, player_id: 1, date_from: "2026-07-01T00:00:00Z", date_to: "2026-08-11T00:00:00Z", description: "Before bootcamp", notes: "", match_count: 31 },
  { id: 40, player_id: 1, date_from: "2026-05-01T00:00:00Z", date_to: "2026-06-30T00:00:00Z", description: "", notes: "", match_count: 44 },
];

const CHAMPIONS = ["Ahri", "Orianna", "Syndra", "Azir", "Viktor", "Ahri", "Taliyah"];
const RESULTS = "011011101011011101101011";
const ITEMS = [6655, 3020, 3089, 4645, 3135, 3157, 3363];

const clamp = (value: number) => Math.min(0.97, Math.max(0.03, value));

function deathEvents(game: number, count: number) {
  return Array.from({ length: count }, (_, index) => {
    const along = ((game * 37 + index * 53) % 100) / 100;
    const jitter = (((game * 13 + index * 29) % 20) - 10) / 100;
    // La mayoría de las muertes caen en el carril central, alguna en la jungla.
    const inJungle = (game + index) % 4 === 0;
    const nx = clamp(inJungle ? 0.3 + jitter : 0.25 + along * 0.5 + jitter / 2);
    const ny = clamp(inJungle ? 0.35 + along / 3 : 0.75 - along * 0.5 + jitter / 3);
    return {
      x: Math.round(nx * MAP_UNITS),
      y: Math.round((1 - ny) * MAP_UNITS),
      norm_x: nx,
      norm_y: ny,
      time: 180 + ((game * 131 + index * 397) % 1800),
      assistingParticipantIds: [],
    };
  });
}

function makeMatch(game: number) {
  const win = RESULTS[game % RESULTS.length] === "1";
  const deaths = ((game * 7) % 6) + 1;
  const kills = 3 + ((game * 5) % 9);
  const assists = 4 + ((game * 3) % 10);
  const duration = 1500 + ((game * 97) % 900);
  const minutes = duration / 60;
  const totalCs = Math.round(minutes * (7.2 + ((game * 3) % 14) / 10));
  const gold = Math.round(minutes * (390 + ((game * 11) % 80)));
  const vision = 18 + (game % 15);
  const damage = Math.round(minutes * (720 + ((game * 23) % 300)));
  const events = deathEvents(game, deaths);
  return {
    match_id: `KR_${7200000 + game}`,
    player_id: 1,
    snapshot_id: 42,
    creation_time: new Date(Date.UTC(2026, 7, 13, 18 + (game % 5)) + game * 86_400_000 * 1.2).toISOString(),
    champion: CHAMPIONS[game % CHAMPIONS.length] ?? "Ahri",
    win,
    duration,
    kills,
    deaths,
    assists,
    kill_participation: 0.48 + ((game * 7) % 30) / 100,
    vision,
    damage,
    gold,
    total_cs: totalCs,
    damage_share: 0.21 + ((game * 3) % 12) / 100,
    first_dragon: game % 2 === 0,
    void_grubs: game % 3 === 0,
    herald: game % 4 === 0,
    summoner1_id: 4,
    summoner2_id: 14,
    item0: ITEMS[0],
    item1: ITEMS[1],
    item2: ITEMS[2],
    item3: game % 3 === 0 ? 0 : ITEMS[3],
    item4: game % 2 === 0 ? ITEMS[4] : 0,
    item5: game % 4 === 0 ? ITEMS[5] : 0,
    item6: ITEMS[6],
    primary_rune: 8112,
    secondary_tree: 8200,
    death_events: [],
    ward_events: [],
    dragon_setups: [],
    solo_kills: game % 3,
    damage_structures: 2500 + game * 90,
    gold_share: 0.23,
    enemy_jg_monsters: game % 5,
    control_wards: 2 + (game % 3),
    roaming_proactivity: game % 4,
    objective_vision_score: 4 + (game % 6),
    early_gank_deaths: game % 3 === 0 ? 1 : 0,
    player_role: "MID",
    role_bound_item: 0,
    quest_completed: false,
    quest_completion_time: null,
    enemy_quest_completion_time: null,
    quest_completion_time_diff: null,
    fullclear_time: null,
    cs_8: 64,
    cs_14: 118,
    cs_25: 212,
    cs_diff_8: 4,
    cs_diff_14: 9,
    cs_diff_25: 15,
    gold_diff_8: 120,
    gold_diff_14: ((game * 173) % 1500) - 450,
    gold_diff_25: 600,
    xp_diff_8: 80,
    xp_diff_14: 210,
    xp_diff_25: 300,
    quest_item_id: 0,
    duration_minutes: Math.round(minutes * 100) / 100,
    kda: Math.round(((kills + assists) / deaths) * 100) / 100,
    cs_per_min: Math.round((totalCs / minutes) * 100) / 100,
    dmg_per_min: Math.round((damage / minutes) * 100) / 100,
    gold_per_min: Math.round((gold / minutes) * 100) / 100,
    fullclear_timer: null,
    vision_per_min: Math.round((vision / minutes) * 100) / 100,
    deaths_by_phase: {},
    death_events_normalized: events,
    ward_events_normalized: [],
    dragon_setups_summary: {},
  };
}

export const matches = Array.from({ length: 24 }, (_, game) => makeMatch(game));

const ROLES = ["TOP", "JUNGLE", "MID", "BOTTOM", "SUPPORT"];
const LINEUPS = [
  { champions: ["Aatrox", "Vi", "Ahri", "Jinx", "Nautilus"], names: ["Zeus", "Oner", "Faker", "Gumayusi", "Keria"] },
  { champions: ["Gnar", "Sejuani", "Azir", "Kaisa", "Rakan"], names: ["Kiin", "Canyon", "Chovy", "Peyz", "Lehends"] },
];

/** Los 10 participantes de una partida del historial; Faker (puuid-1) es el jugador seguido. */
export function matchDetails(matchId: string) {
  const game = Math.max(0, matches.findIndex((m) => m.match_id === matchId));
  const base = matches[game] ?? makeMatch(0);
  const minutes = base.duration / 60;
  const teams = [100, 200].map((teamId, side) => {
    const win = side === 0 ? base.win : !base.win;
    const lineup = LINEUPS[side] ?? LINEUPS[0];
    const participants = ROLES.map((role, slot) => {
      const tracked = side === 0 && slot === 2;
      const kills = tracked ? base.kills : (game + slot * 3 + side) % 8;
      const deaths = tracked ? base.deaths : 1 + ((game + slot + side * 2) % 6);
      const assists = tracked ? base.assists : 2 + ((game * 2 + slot) % 11);
      const cs = role === "SUPPORT" ? 38 : role === "JUNGLE" ? 190 : tracked ? base.total_cs : 210 + slot * 12;
      const damage = tracked ? base.damage : Math.round(minutes * (380 + ((slot * 131 + side * 57) % 520)));
      const vision = role === "SUPPORT" ? 72 : 16 + slot * 3;
      return {
        puuid: tracked ? "puuid-1" : `puuid-${side}-${slot}`,
        game_name: lineup.names[slot] ?? "Player",
        tag_line: side === 0 ? "KR1" : "KR2",
        champion: tracked ? base.champion : (lineup.champions[slot] ?? "Ahri"),
        champion_level: 14 + ((slot + side) % 5),
        team_id: teamId,
        role,
        win,
        kills,
        deaths,
        assists,
        kda: Math.round(((kills + assists) / Math.max(deaths, 1)) * 100) / 100,
        kill_participation: 40 + ((slot * 9 + side * 5) % 35),
        cs,
        cs_per_min: Math.round((cs / minutes) * 10) / 10,
        gold: Math.round(minutes * (300 + slot * 25)),
        damage,
        damage_per_min: Math.round((damage / minutes) * 10) / 10,
        damage_share: 20,
        damage_taken: 18_000 + slot * 1500,
        vision_score: vision,
        vision_per_min: Math.round((vision / minutes) * 100) / 100,
        wards_placed: role === "SUPPORT" ? 34 : 8,
        control_wards: role === "SUPPORT" ? 9 : 2,
        items: ITEMS.slice(0, 6).map((item, index) => (index <= 3 + (slot % 3) ? item : 0)),
        trinket: ITEMS[6] ?? 0,
        spells: [4, 14],
        keystone: 8112,
        secondary_tree: 8100,
        score: 0,
        placement: 0,
        badge: null as "MVP" | "ACE" | null,
      };
    });
    return {
      team_id: teamId,
      win,
      kills: participants.reduce((sum, p) => sum + p.kills, 0),
      towers: win ? 9 : 3,
      inhibitors: win ? 2 : 0,
      dragons: win ? 3 : 1,
      barons: win ? 1 : 0,
      heralds: win ? 1 : 0,
      grubs: win ? 4 : 2,
      atakhans: 0,
      participants,
    };
  });

  // Nota de mentira por KDA y daño entre 35 y 90; MVP para el mejor ganador y ACE para el mejor perdedor.
  const everyone = teams.flatMap((team) => team.participants);
  const raw = everyone.map((p) => p.kda + p.damage_per_min / 200);
  const best = Math.max(...raw);
  everyone.forEach((p, index) => (p.score = Math.round(35 + ((raw[index] ?? 0) / best) * 55)));
  [...everyone].sort((a, b) => b.score - a.score).forEach((p, index) => (p.placement = index + 1));
  for (const team of teams) {
    const [top] = [...team.participants].sort((a, b) => a.placement - b.placement);
    top.badge = team.win ? "MVP" : "ACE";
  }

  return {
    match_id: matchId,
    creation_time: base.creation_time,
    duration: base.duration,
    queue_id: 420,
    game_version: "16.10.1",
    teams,
  };
}

function movingAverage(values: number[], window = 4): number[] {
  return values.map((_, index) => {
    const chunk = values.slice(Math.max(0, index - window + 1), index + 1);
    return Math.round((chunk.reduce((sum, value) => sum + value, 0) / chunk.length) * 100) / 100;
  });
}

const kda = movingAverage(matches.map((m) => m.kda));
const cs = movingAverage(matches.map((m) => m.cs_per_min));
const goldAvg = movingAverage(matches.map((m) => m.gold_per_min));
const visionAvg = movingAverage(matches.map((m) => m.vision_per_min));

const AXES = ["KDA", "CS/min", "Gold @14", "Kill part.", "Damage", "Vision", "Deaths"];
const RANK_SCORES: Record<string, number> = {
  IRON: 18, BRONZE: 28, SILVER: 38, GOLD: 48, PLATINUM: 55, EMERALD: 61, DIAMOND: 68, MASTER: 74, GRANDMASTER: 78, CHALLENGER: 82,
};

const dataset = (label: string, scores: number[]) => ({
  label,
  values: Object.fromEntries(AXES.map((axis, index) => [axis, Math.round((scores[index] ?? 50) / 12 * 100) / 100])),
  normalized_values: Object.fromEntries(AXES.map((axis, index) => [axis, scores[index] ?? 50])),
});

function dashboardFor(snapshot: (typeof snapshots)[number], scores: number[], shift: number) {
  const metric = (key: string, label: string, value: number, status: string, threshold: number, unit = "") => ({
    key, label, value: Math.round((value - shift * (key === "deaths" ? -0.4 : value / 12)) * 100) / 100, status, threshold, unit,
  });
  return {
    snapshot_id: snapshot.id,
    player_id: 1,
    player_name: "Faker",
    date_from: snapshot.date_from,
    date_to: snapshot.date_to,
    description: snapshot.description,
    notes: snapshot.id === 42 ? "Trading much better in lane. Still dying to jungle ganks after first back." : "",
    active_role: "MID",
    games_played: snapshot.match_count,
    role_averages: [
      metric("kda", "KDA", 3.94, shift ? "normal" : "good", 3.5),
      metric("cs_per_min", "CS per minute", 8.12, "good", 8),
      metric("gold_diff_14", "Gold diff @14", 312, shift ? "normal" : "excellent", 250),
      metric("kill_participation", "Kill participation", 64.2, "good", 60, "%"),
      metric("damage_share", "Damage share", 27.5, "excellent", 26, "%"),
      metric("vision_per_min", "Vision per minute", 0.92, "normal", 1),
      metric("deaths", "Deaths", 3.4, shift ? "bad" : "normal", 3.5),
      metric("early_gank_deaths", "Deaths to ganks <14'", 0.9, "bad", 0.5),
    ],
    played_champions: [
      { champion_name: "Ahri", games_played: 7, win_rate: 71.4, icon_url: "" },
      { champion_name: "Orianna", games_played: 4, win_rate: 50, icon_url: "" },
      { champion_name: "Syndra", games_played: 4, win_rate: 75, icon_url: "" },
      { champion_name: "Azir", games_played: 3, win_rate: 33.3, icon_url: "" },
      { champion_name: "Viktor", games_played: 3, win_rate: 66.7, icon_url: "" },
      { champion_name: "Taliyah", games_played: 3, win_rate: 33.3, icon_url: "" },
    ],
    deaths_by_phase: { early_deaths: 11 + shift * 4, mid_deaths: 26 + shift * 6, late_deaths: 45 },
    performance_trends: matches.map((m, index) => ({
      game_num: index + 1,
      match_id: m.match_id,
      creation_time: m.creation_time,
      champion: m.champion,
      win: m.win,
      kda: m.kda,
      cs_per_min: m.cs_per_min,
      gold_per_min: m.gold_per_min,
      vision_per_min: m.vision_per_min,
      kda_moving_avg: kda[index] ?? 0,
      cs_moving_avg: cs[index] ?? 0,
      gold_moving_avg: goldAvg[index] ?? 0,
      vision_moving_avg: visionAvg[index] ?? 0,
    })),
    radar_data: {
      axes: AXES,
      player_dataset: dataset("Faker", scores),
      rank_datasets: Object.fromEntries(
        Object.entries(RANK_SCORES).map(([tier, score]) => [
          tier,
          dataset(tier.charAt(0) + tier.slice(1).toLowerCase(), AXES.map(() => score)),
        ]),
      ),
      pro_datasets: {},
    },
  };
}

const [latest, previous, oldest] = snapshots;

export const dashboards: Partial<Record<number, ReturnType<typeof dashboardFor>>> = {
  42: dashboardFor(latest, [78, 74, 86, 71, 80, 58, 63], 0),
  41: dashboardFor(previous, [69, 72, 64, 66, 75, 55, 49], 1),
  40: dashboardFor(oldest, [61, 70, 58, 60, 70, 52, 45], 1),
};

export const roleSummary = [
  { role: "MID", games: 164, win_rate: 56.1, kda: 3.81, cs_per_min: 8.04, gold_diff_14: 268, deaths: 3.5 },
  { role: "TOP", games: 21, win_rate: 47.6, kda: 2.64, cs_per_min: 7.21, gold_diff_14: -85, deaths: 4.4 },
  { role: "SUPPORT", games: 6, win_rate: 33.3, kda: 2.1, cs_per_min: 1.2, gold_diff_14: null, deaths: 5.2 },
];

const champion = (champion_name: string, wins: number, losses: number, kda: number, cs: number, dpm: number, vision: number) => ({
  champion_name,
  games: wins + losses,
  wins,
  losses,
  win_rate: Math.round((wins / (wins + losses)) * 1000) / 10,
  kills: 6.1,
  deaths: 3.2,
  assists: 7.4,
  kda,
  cs_per_min: cs,
  dmg_per_min: dpm,
  vision_score: vision,
});

export const championStats = [
  champion("Ahri", 21, 13, 4.24, 8.3, 812, 24.6),
  champion("Orianna", 12, 9, 3.61, 8.1, 745, 26.1),
  champion("Syndra", 11, 5, 3.92, 7.9, 901, 21.8),
  champion("Azir", 6, 7, 2.87, 8.6, 688, 23.4),
  champion("Viktor", 7, 4, 3.35, 8.0, 790, 22.0),
  champion("Taliyah", 3, 4, 2.54, 7.2, 655, 25.9),
];

export const cutoffs = (region: string) => ({
  region,
  platform: region === "KR" ? "kr" : `${region.toLowerCase()}1`,
  grandmaster_cutoff_lp: region === "KR" ? 612 : 348,
  challenger_cutoff_lp: region === "KR" ? 1034 : 811,
  fetched_at: "2026-09-10T22:15:00Z",
});

export const ddragonSpells = {
  SummonerFlash: { key: "4", image: { full: "SummonerFlash.png" } },
  SummonerDot: { key: "14", image: { full: "SummonerDot.png" } },
};

export const ddragonRunes = [
  {
    id: 8100,
    icon: "perk-images/Styles/7200_Domination.png",
    slots: [{ runes: [{ id: 8112, icon: "perk-images/Styles/Domination/Electrocute/Electrocute.png" }] }],
  },
];

export const adminStats = {
  total_users: 38,
  active_users: 33,
  inactive_users: 5,
  total_players: 142,
  total_snapshots: 391,
  total_matches: 12876,
  tier_distribution: [
    { tier: "CHALLENGER", count: 3 }, { tier: "GRANDMASTER", count: 6 }, { tier: "MASTER", count: 14 }, { tier: "DIAMOND", count: 31 },
    { tier: "EMERALD", count: 38 }, { tier: "PLATINUM", count: 24 }, { tier: "GOLD", count: 15 }, { tier: "", count: 11 },
  ],
  region_distribution: [
    { region: "EUW", count: 71 }, { region: "KR", count: 28 }, { region: "NA", count: 22 }, { region: "EUNE", count: 21 },
  ],
  top_users: [
    { username: "coach", player_count: 24 }, { username: "analyst_mia", player_count: 18 }, { username: "academy", player_count: 11 },
  ],
};

export const adminUsers = [
  adminUser,
  { id: 2, email: "mia@ygg.gg", username: "analyst_mia", role: "user", is_active: true },
  { id: 3, email: "academy@ygg.gg", username: "academy", role: "user", is_active: true },
  { id: 4, email: "old@ygg.gg", username: "former_sub", role: "user", is_active: false },
];

export const adminPlayers = players.map((p, index) => ({
  id: p.id, game_name: p.game_name, tag_line: p.tag_line, region: p.region, nickname: p.nickname, role: p.role,
  tier: p.tier, rank: p.rank, lp: p.lp, wins: p.wins, losses: p.losses, owner_username: adminUsers[index % 3].username,
}));

const job = (status: string, progress: number, snapshotId: number | null = null) => ({
  job_id: "job-1",
  status,
  progress,
  snapshot_id: snapshotId,
  error: null,
  attempts: 1,
});

export const jobStream = [
  `event: progress\ndata: ${JSON.stringify(job("queued", 0))}\n\n`,
  `event: progress\ndata: ${JSON.stringify(job("processing", 55))}\n\n`,
  `event: done\ndata: ${JSON.stringify(job("done", 100, 42))}\n\n`,
].join("");
