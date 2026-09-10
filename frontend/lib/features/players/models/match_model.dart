class DeathEvent {
  const DeathEvent({
    required this.x,
    required this.y,
    required this.time,
    this.normX = 0.0,
    this.normY = 0.0,
    this.assistingParticipantIds = const [],
  });
  final int    x;
  final int    y;
  final int    time;
  final double normX;
  final double normY;
  final List<int> assistingParticipantIds;

  factory DeathEvent.fromJson(Map<String, dynamic> j) => DeathEvent(
    x:     j['x']     as int? ?? 0,
    y:     j['y']     as int? ?? 0,
    time:  j['time']  as int? ?? 0,
    normX: (j['norm_x'] as num?)?.toDouble() ?? 0.0,
    normY: (j['norm_y'] as num?)?.toDouble() ?? 0.0,
    assistingParticipantIds: (j['assistingParticipantIds'] as List<dynamic>?)
        ?.map((e) => (e as num?)?.toInt())
        .whereType<int>()
        .toList() ?? const [],
  );
}

class WardEvent {
  const WardEvent({
    required this.x,
    required this.y,
    required this.time,
    this.normX = 0.0,
    this.normY = 0.0,
    this.type = 'unknown',
  });
  final int    x;
  final int    y;
  final int    time;
  final double normX;
  final double normY;
  final String type;

  factory WardEvent.fromJson(Map<String, dynamic> j) => WardEvent(
    x:     j['x']     as int? ?? 0,
    y:     j['y']     as int? ?? 0,
    time:  j['time']  as int? ?? 0,
    normX: (j['norm_x'] as num?)?.toDouble() ?? 0.0,
    normY: (j['norm_y'] as num?)?.toDouble() ?? 0.0,
    type:  j['type']  as String? ?? 'unknown',
  );
}

class DragonSetup {
  const DragonSetup({
    required this.dragonTime,
    this.dragonType = 'UNKNOWN',
    this.teamDragon = false,
    this.inPrepZone = false,
    this.atKillZone = false,
    this.securedByJg = false,
    this.contested = false,
  });

  final int    dragonTime;
  final String dragonType;
  final bool   teamDragon;
  final bool   inPrepZone;
  final bool   atKillZone;
  final bool   securedByJg;
  final bool   contested;

  factory DragonSetup.fromJson(Map<String, dynamic> j) => DragonSetup(
    dragonTime:  j['dragon_time']   as int? ?? 0,
    dragonType:  j['dragon_type']  as String? ?? 'UNKNOWN',
    teamDragon:  j['team_dragon']   as bool? ?? false,
    inPrepZone:  j['in_prep_zone']  as bool? ?? false,
    atKillZone:  j['at_kill_zone']  as bool? ?? false,
    securedByJg: j['secured_by_jg'] as bool? ?? false,
    contested:   j['contested']     as bool? ?? false,
  );

  String get minuteLabel {
    final m = dragonTime ~/ 60;
    final s = dragonTime % 60;
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }
}

class MatchModel {
  const MatchModel({
    required this.matchId,
    required this.champion,
    required this.win,
    required this.duration,
    required this.kills,
    required this.deaths,
    required this.assists,
    required this.killParticipation,
    required this.vision,
    required this.totalCs,
    required this.damage,
    required this.gold,
    required this.damageShare,
    required this.goldShare,
    required this.item0,
    required this.item1,
    required this.item2,
    required this.item3,
    required this.item4,
    required this.item5,
    required this.item6,
    required this.summoner1Id,
    required this.summoner2Id,
    required this.primaryRune,
    required this.secondaryTree,
    required this.creationTime,
    this.goldDiff8,
    this.goldDiff14,
    this.goldDiff25,
    this.csDiff8,
    this.csDiff14,
    this.csDiff25,
    this.xpDiff8,
    this.xpDiff14,
    this.earlyGankDeaths = 0,
    this.deathEvents = const [],
    this.wardEvents = const [],
    this.dragonSetups = const [],
    this.soloKills = 0,
    this.damageStructures = 0,
    this.enemyJgMonsters = 0,
    this.controlWards = 0,
    this.roamingProactivity = 0,
    this.objectiveVisionScore = 0,
    this.firstDragon = false,
    this.voidGrubs = false,
    this.herald = false,
    this.questCompleted,
    this.questCompletionTime,
    this.enemyQuestCompletionTime,
    this.questCompletionTimeDiff,
    this.roleBoundItem = 0,
    this.questItemId = 0,
    this.playerRole,
  });

  // ── Identificación ────────────────────────────────────────────────────────
  final String   matchId;
  final String   champion;
  final bool     win;
  final int      duration;
  final DateTime creationTime;

  // ── Combate ───────────────────────────────────────────────────────────────
  final int    kills;
  final int    deaths;
  final int    assists;
  final double killParticipation;
  final int    vision;
  final int    totalCs;
  final int    damage;
  final int    gold;

  // ── Eficiencia (scatter plot) ─────────────────────────────────────────────
  final double damageShare;   // % del daño total del equipo  — eje Y scatter
  final double goldShare;     // % del oro total del equipo   — eje X scatter

  // ── Control de carril (zero-baseline) ────────────────────────────────────
  final int? goldDiff8;
  final int? goldDiff14;
  final int? goldDiff25;
  final int? csDiff8;
  final int? csDiff14;
  final int? csDiff25;
  final int? xpDiff8;
  final int? xpDiff14;

  // ── Equipamiento ─────────────────────────────────────────────────────────
  final int item0, item1, item2, item3, item4, item5, item6;
  final int summoner1Id;
  final int summoner2Id;
  final int primaryRune;
  final int secondaryTree;

  // ── Fase temprana ─────────────────────────────────────────────────────────
  final int earlyGankDeaths;

  // ── Mapa de calor ─────────────────────────────────────────────────────────
  final List<DeathEvent> deathEvents;
  final List<WardEvent> wardEvents;
  final List<DragonSetup> dragonSetups;

  // ── Estadísticas Avanzadas para Dashboard ──────────────────────────────────
  final int soloKills;
  final int damageStructures;
  final int enemyJgMonsters;
  final int controlWards;
  final int roamingProactivity;
  final int objectiveVisionScore;
  final bool firstDragon;
  final bool voidGrubs;
  final bool herald;

  // ── Role Quests (Season 26) ───────────────────────────────────────────────
  final bool? questCompleted;
  final int? questCompletionTime;
  final int? enemyQuestCompletionTime;
  final int? questCompletionTimeDiff;
  final int roleBoundItem;
  final int questItemId;
  final String? playerRole;

  static const _adcRoleBoundItems = {3020, 3006, 3008, 3047};
  static const _defaultRoleBoundItems = {
    'TOP': 1220,
    'MID': 1206,
    'JUNGLE': 1209,
    'SUPPORT': 1208,
    'ADC': 3020,
  };

  bool get isSeason26 => creationTime.isAfter(DateTime(2026));

  /// Item id used for the quest reward icon in match history.
  int get questDisplayItemId {
    if (questItemId > 0) return questItemId;
    if (roleBoundItem > 0) return roleBoundItem;
    if (!isSeason26) return 0;
    for (final id in buildItems) {
      if (_adcRoleBoundItems.contains(id)) return id;
    }
    final role = playerRole?.toUpperCase();
    if (role != null) return _defaultRoleBoundItems[role] ?? 0;
    return 0;
  }

  static String formatQuestTime(int seconds) =>
      '${seconds ~/ 60}m ${(seconds % 60).toString().padLeft(2, '0')}s';

  static String formatQuestDiff(int seconds) {
    final sign = seconds >= 0 ? '+' : '-';
    final abs = seconds.abs();
    if (abs >= 60) {
      return '$sign${abs ~/ 60}m ${(abs % 60).toString().padLeft(2, '0')}s';
    }
    return '$sign${abs}s';
  }

  List<DragonSetup> get teamDragonSetups =>
      dragonSetups.where((d) => d.teamDragon).toList();

  double? get dragonSetupRate {
    final team = teamDragonSetups;
    if (team.isEmpty) return null;
    return team.where((d) => d.inPrepZone).length / team.length * 100;
  }

  double? get dragonPresenceRate {
    final team = teamDragonSetups;
    if (team.isEmpty) return null;
    return team.where((d) => d.atKillZone).length / team.length * 100;
  }

  double? get dragonSecureRate {
    final team = teamDragonSetups;
    if (team.isEmpty) return null;
    return team.where((d) => d.securedByJg).length / team.length * 100;
  }

  // ── Computed ──────────────────────────────────────────────────────────────
  double get kdaValue  => deaths == 0 ? (kills + assists).toDouble() : (kills + assists) / deaths;
  double get csPerMin  => duration > 0 ? totalCs / (duration / 60) : 0;
  double get dmgPerMin => duration > 0 ? damage  / (duration / 60) : 0;
  double get goldPerMin => duration > 0 ? gold   / (duration / 60) : 0;

  List<int> get buildItems => [item0, item1, item2, item3, item4, item5];
  int       get trinket    => item6;

  factory MatchModel.fromJson(Map<String, dynamic> j) => MatchModel(
    matchId:          j['match_id']           as String,
    champion:         j['champion']            as String,
    win:              j['win']                 as bool? ?? false,
    duration:         _readInt(j['duration']),
    kills:            _readInt(j['kills']),
    deaths:           _readInt(j['deaths']),
    assists:          _readInt(j['assists']),
    killParticipation:(j['kill_participation']  as num?)?.toDouble() ?? 0.0,
    vision:           _readInt(j['vision']),
    totalCs:          _readInt(j['total_cs']),
    damage:           j['damage']              as int? ?? 0,
    gold:             j['gold']                as int? ?? 0,
    damageShare:     (j['damage_share']         as num?)?.toDouble() ?? 0.0,
    goldShare:       (j['gold_share']           as num?)?.toDouble() ?? 0.0,
    item0:            j['item0']               as int? ?? 0,
    item1:            j['item1']               as int? ?? 0,
    item2:            j['item2']               as int? ?? 0,
    item3:            j['item3']               as int? ?? 0,
    item4:            j['item4']               as int? ?? 0,
    item5:            j['item5']               as int? ?? 0,
    item6:            j['item6']               as int? ?? 0,
    summoner1Id:      j['summoner1_id']        as int? ?? 0,
    summoner2Id:      j['summoner2_id']        as int? ?? 0,
    primaryRune:      j['primary_rune']        as int? ?? 0,
    secondaryTree:    j['secondary_tree']      as int? ?? 0,
    creationTime:     DateTime.parse(j['creation_time'] as String).toLocal(),
    goldDiff8:        j['gold_diff_8']         as int?,
    goldDiff14:       j['gold_diff_14']        as int?,
    goldDiff25:       j['gold_diff_25']        as int?,
    csDiff8:          j['cs_diff_8']           as int?,
    csDiff14:         j['cs_diff_14']          as int?,
    csDiff25:         j['cs_diff_25']          as int?,
    xpDiff8:          j['xp_diff_8']           as int?,
    xpDiff14:         j['xp_diff_14']          as int?,
    earlyGankDeaths:  j['early_gank_deaths']   as int? ?? 0,
    deathEvents: (j['death_events_normalized'] as List<dynamic>? ?? [])
        .map((e) => DeathEvent.fromJson(e as Map<String, dynamic>))
        .toList(),
    wardEvents: (j['ward_events_normalized'] as List<dynamic>? ?? [])
        .map((e) => WardEvent.fromJson(e as Map<String, dynamic>))
        .toList(),
    dragonSetups: (j['dragon_setups'] as List<dynamic>? ?? [])
        .map((e) => DragonSetup.fromJson(e as Map<String, dynamic>))
        .toList(),
    soloKills:        j['solo_kills']          as int? ?? 0,
    damageStructures: j['damage_structures']   as int? ?? 0,
    enemyJgMonsters:  j['enemy_jg_monsters']   as int? ?? 0,
    controlWards:     j['control_wards']       as int? ?? 0,
    roamingProactivity:j['roaming_proactivity'] as int? ?? 0,
    objectiveVisionScore: j['objective_vision_score'] as int? ?? 0,
    firstDragon:      j['first_dragon']        as bool? ?? false,
    voidGrubs:        j['void_grubs']          as bool? ?? false,
    herald:           j['herald']              as bool? ?? false,
    questCompleted:   j['quest_completed']     as bool?,
    questCompletionTime: j['quest_completion_time'] as int?,
    enemyQuestCompletionTime: j['enemy_quest_completion_time'] as int?,
    questCompletionTimeDiff: j['quest_completion_time_diff'] as int?,
    roleBoundItem:    j['role_bound_item']     as int? ?? 0,
    questItemId:      j['quest_item_id']       as int? ?? 0,
    playerRole:       j['player_role']         as String?,
  );

  static int _readInt(dynamic value, [int fallback = 0]) {
    if (value == null) return fallback;
    if (value is int) return value;
    if (value is num) return value.toInt();
    return fallback;
  }
}
