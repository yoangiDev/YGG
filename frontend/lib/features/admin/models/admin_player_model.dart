class AdminPlayerModel {
  const AdminPlayerModel({
    required this.id,
    required this.gameName,
    required this.tagLine,
    required this.region,
    required this.nickname,
    required this.role,
    required this.tier,
    required this.rank,
    required this.lp,
    required this.wins,
    required this.losses,
    required this.ownerUsername,
  });

  final int    id;
  final String gameName;
  final String tagLine;
  final String region;
  final String nickname;
  final String role;
  final String tier;
  final String rank;
  final int    lp;
  final int    wins;
  final int    losses;
  final String ownerUsername;

  String get riotId => '$gameName#$tagLine';

  double get winRate {
    final total = wins + losses;
    if (total == 0) return 0.0;
    return (wins / total) * 100;
  }

  factory AdminPlayerModel.fromJson(Map<String, dynamic> j) => AdminPlayerModel(
    id:            j['id']             as int,
    gameName:      j['game_name']      as String,
    tagLine:       j['tag_line']       as String,
    region:        j['region']         as String,
    nickname:      j['nickname']       as String? ?? '',
    role:          j['role']           as String? ?? '',
    tier:          j['tier']           as String? ?? '',
    rank:          j['rank']           as String? ?? '',
    lp:            j['lp']             as int?    ?? 0,
    wins:          j['wins']           as int?    ?? 0,
    losses:        j['losses']         as int?    ?? 0,
    ownerUsername: j['owner_username'] as String,
  );
}
