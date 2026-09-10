class SnapshotStatsModel {
  const SnapshotStatsModel({
    required this.snapshotId,
    required this.gamesPlayed,
    required this.winrate,
    required this.avgKda,
    required this.avgCsPerMin,
    required this.avgDamagePerMin,
    required this.avgGoldPerMin,
    required this.avgVision,
    required this.avgKillParticipation,
    required this.firstDragonRate,
    required this.heraldRate,
    required this.voidGrubsRate,
  });

  final int    snapshotId;
  final int    gamesPlayed;
  final double winrate;
  final double avgKda;
  final double avgCsPerMin;
  final double avgDamagePerMin;
  final double avgGoldPerMin;
  final double avgVision;
  final double avgKillParticipation;
  final String firstDragonRate;
  final String heraldRate;
  final String voidGrubsRate;

  factory SnapshotStatsModel.fromJson(Map<String, dynamic> j) => SnapshotStatsModel(
    snapshotId:           j['snapshot_id']              as int,
    gamesPlayed:          j['games_played']             as int,
    winrate:             (j['winrate']                  as num).toDouble(),
    avgKda:              (j['avg_kda']                  as num).toDouble(),
    avgCsPerMin:         (j['avg_cs_per_min']           as num).toDouble(),
    avgDamagePerMin:     (j['avg_damage_per_min']       as num).toDouble(),
    avgGoldPerMin:       (j['avg_gold_per_min']         as num).toDouble(),
    avgVision:           (j['avg_vision']               as num).toDouble(),
    avgKillParticipation:(j['avg_kill_participation']   as num).toDouble(),
    firstDragonRate:      j['first_dragon_rate']        as String,
    heraldRate:           j['herald_rate']              as String,
    voidGrubsRate:        j['two_or_more_void_grubs_rate'] as String,
  );
}
