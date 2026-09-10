class RadarDataset {
  const RadarDataset({
    required this.label,
    required this.values,
    required this.normalizedValues,
  });

  final String              label;
  final Map<String, double> values;           // valores reales  — ej. {"KDA": 4.2}
  final Map<String, double> normalizedValues; // 0-100 para el radar — ej. {"KDA": 70.0}

  factory RadarDataset.fromJson(Map<String, dynamic> j) => RadarDataset(
    label:            j['label'] as String,
    values:           (j['values'] as Map<String, dynamic>)
        .map((k, v) => MapEntry(k, (v as num).toDouble())),
    normalizedValues: (j['normalized_values'] as Map<String, dynamic>)
        .map((k, v) => MapEntry(k, (v as num).toDouble())),
  );
}

class RadarChartData {
  const RadarChartData({
    required this.axes,
    required this.playerDataset,
    required this.rankDatasets,
    required this.proDatasets,
  });

  final List<String>              axes;           // nombres de los 6 ejes
  final RadarDataset              playerDataset;
  final Map<String, RadarDataset> rankDatasets;   // "CHALLENGER", "DIAMOND", etc.
  final Map<String, RadarDataset> proDatasets;    // nombre de proplayer → dataset

  factory RadarChartData.fromJson(Map<String, dynamic> j) => RadarChartData(
    axes: (j['axes'] as List<dynamic>).map((e) => e as String).toList(),
    playerDataset: RadarDataset.fromJson(j['player_dataset'] as Map<String, dynamic>),
    rankDatasets: (j['rank_datasets'] as Map<String, dynamic>)
        .map((k, v) => MapEntry(k, RadarDataset.fromJson(v as Map<String, dynamic>))),
    proDatasets: (j['pro_datasets'] as Map<String, dynamic>)
        .map((k, v) => MapEntry(k, RadarDataset.fromJson(v as Map<String, dynamic>))),
  );
}

class TrendPoint {
  const TrendPoint({
    required this.gameNum,
    required this.matchId,
    required this.creationTime,
    required this.champion,
    required this.win,
    required this.kda,
    required this.csPerMin,
    required this.goldPerMin,
    required this.visionPerMin,
    required this.kdaMovingAvg,
    required this.csMovingAvg,
    required this.goldMovingAvg,
    required this.visionMovingAvg,
  });

  final int      gameNum;
  final String   matchId;
  final DateTime creationTime;
  final String   champion;
  final bool     win;
  final double   kda;
  final double   csPerMin;
  final double   goldPerMin;
  final double   visionPerMin;
  final double   kdaMovingAvg;
  final double   csMovingAvg;
  final double   goldMovingAvg;
  final double   visionMovingAvg;

  factory TrendPoint.fromJson(Map<String, dynamic> j) => TrendPoint(
    gameNum:       j['game_num']        as int? ?? 0,
    matchId:       j['match_id']        as String? ?? '',
    creationTime:  j['creation_time'] != null ? DateTime.parse(j['creation_time'] as String).toLocal() : DateTime.now(),
    champion:      j['champion']        as String? ?? '',
    win:           j['win']             as bool? ?? false,
    kda:           ((j['kda'] ?? 0.0) as num).toDouble(),
    csPerMin:      ((j['cs_per_min'] ?? 0.0) as num).toDouble(),
    goldPerMin:    ((j['gold_per_min'] ?? 0.0) as num).toDouble(),
    visionPerMin:  ((j['vision_per_min'] ?? 0.0) as num).toDouble(),
    kdaMovingAvg:  ((j['kda_moving_avg'] ?? 0.0) as num).toDouble(),
    csMovingAvg:   ((j['cs_moving_avg'] ?? 0.0) as num).toDouble(),
    goldMovingAvg: ((j['gold_moving_avg'] ?? 0.0) as num).toDouble(),
    visionMovingAvg: ((j['vision_moving_avg'] ?? 0.0) as num).toDouble(),
  );
}

class SnapshotDashboardModel {
  const SnapshotDashboardModel({
    required this.snapshotId,
    required this.activeRole,
    required this.radarData,
    this.performanceTrends = const [],
  });

  final int              snapshotId;
  final String           activeRole;        // "TOP" | "JUNGLE" | "MID" | "ADC" | "SUPPORT"
  final RadarChartData   radarData;
  final List<TrendPoint> performanceTrends; // serie cronológica con medias móviles (ventana 3)

  factory SnapshotDashboardModel.fromJson(Map<String, dynamic> j) =>
      SnapshotDashboardModel(
        snapshotId: j['snapshot_id'] as int,
        activeRole: j['active_role'] as String,
        radarData:  RadarChartData.fromJson(j['radar_data'] as Map<String, dynamic>),
        performanceTrends: (j['performance_trends'] as List<dynamic>? ?? [])
            .map((e) => TrendPoint.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
