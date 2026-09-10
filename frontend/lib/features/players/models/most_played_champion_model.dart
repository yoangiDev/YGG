class MostPlayedChampion {
  const MostPlayedChampion({
    required this.championName,
    required this.gamesPlayed,
    required this.winRate,
    required this.iconUrl,
  });

  final String championName;
  final int    gamesPlayed;
  final double winRate;
  final String iconUrl;

  factory MostPlayedChampion.fromJson(Map<String, dynamic> j) => MostPlayedChampion(
    championName: j['champion_name'] as String,
    gamesPlayed:  (j['games_played'] as num?)?.toInt() ?? 0,
    winRate:      (j['win_rate']     as num?)?.toDouble() ?? 0.0,
    iconUrl:      j['icon_url']      as String? ?? '',
  );
}
