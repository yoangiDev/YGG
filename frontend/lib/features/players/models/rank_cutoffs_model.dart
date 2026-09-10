class RankCutoffs {
  const RankCutoffs({
    required this.region,
    required this.platform,
    required this.grandmasterCutoffLp,
    required this.challengerCutoffLp,
    required this.fetchedAt,
  });

  final String region;
  final String platform;
  final int grandmasterCutoffLp;
  final int challengerCutoffLp;
  final DateTime fetchedAt;

  factory RankCutoffs.fromJson(Map<String, dynamic> json) => RankCutoffs(
    region:               json['region'] as String,
    platform:             json['platform'] as String,
    grandmasterCutoffLp:  json['grandmaster_cutoff_lp'] as int,
    challengerCutoffLp:   json['challenger_cutoff_lp'] as int,
    fetchedAt:            DateTime.parse(json['fetched_at'] as String),
  );

  Map<String, dynamic> toJson() => {
    'region':                 region,
    'platform':               platform,
    'grandmaster_cutoff_lp':  grandmasterCutoffLp,
    'challenger_cutoff_lp':  challengerCutoffLp,
    'fetched_at':             fetchedAt.toIso8601String(),
  };
}
