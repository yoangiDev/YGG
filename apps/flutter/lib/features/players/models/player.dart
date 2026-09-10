class Player {
  const Player({
    required this.id,
    required this.puuid,
    required this.gameName,
    required this.tagLine,
    required this.region,
    required this.nickname,
    required this.role,
    required this.notes,
    required this.tier,
    required this.rank,
    required this.lp,
    required this.profileIconId,
    required this.wins,
    required this.losses,
    required this.winRate,
  });

  final int    id;
  final String puuid;
  final String gameName;
  final String tagLine;
  final String region;
  final String nickname;
  final String role;
  final String notes;
  final String tier;
  final String rank;
  final int    lp;
  final int    profileIconId;
  final int    wins;
  final int    losses;
  final double winRate;

  String get riotId      => '$gameName#$tagLine';
  int    get gamesPlayed => wins + losses;

  String profileIconUrl(String version) =>
      'https://ddragon.leagueoflegends.com/cdn/$version/img/profileicon/$profileIconId.png';

  factory Player.fromJson(Map<String, dynamic> json) => Player(
    id:            json['id']              as int,
    puuid:         json['puuid']           as String,
    gameName:      json['game_name']       as String,
    tagLine:       json['tag_line']        as String,
    region:        json['region']          as String,
    nickname:      json['nickname']        as String? ?? '',
    role:          json['role']            as String? ?? 'TOP',
    notes:         json['notes']           as String? ?? '',
    tier:          json['tier']            as String? ?? '',
    rank:          json['rank']            as String? ?? '',
    lp:            json['lp']             as int? ?? 0,
    profileIconId: json['profile_icon_id'] as int? ?? 0,
    wins:          json['wins']            as int? ?? 0,
    losses:        json['losses']          as int? ?? 0,
    winRate:       (json['win_rate']       as num?)?.toDouble() ?? 0.0,
  );

  Player copyWith({
    String? nickname,
    String? role,
    String? notes,
    String? tier,
    String? rank,
    int?    lp,
    int?    profileIconId,
    int?    wins,
    int?    losses,
    double? winRate,
  }) => Player(
    id:            id,
    puuid:         puuid,
    gameName:      gameName,
    tagLine:       tagLine,
    region:        region,
    nickname:      nickname      ?? this.nickname,
    role:          role          ?? this.role,
    notes:         notes         ?? this.notes,
    tier:          tier          ?? this.tier,
    rank:          rank          ?? this.rank,
    lp:            lp            ?? this.lp,
    profileIconId: profileIconId ?? this.profileIconId,
    wins:          wins          ?? this.wins,
    losses:        losses        ?? this.losses,
    winRate:       winRate       ?? this.winRate,
  );
}

// ── Datos para crear un jugador (POST /players/) ──────────────────────────────

class PlayerCreateData {
  const PlayerCreateData({
    required this.gameName,
    required this.tagLine,
    required this.region,
    this.nickname = '',
    this.role     = 'TOP',
    this.notes    = '',
  });

  final String gameName;
  final String tagLine;
  final String region;
  final String nickname;
  final String role;
  final String notes;

  Map<String, dynamic> toJson() => {
    'game_name': gameName,
    'tag_line':  tagLine,
    'region':    region,
    'nickname':  nickname,
    'role':      role,
    'notes':     notes,
  };
}

// ── Datos para actualizar un jugador (PUT /players/{id}) ─────────────────────

class PlayerUpdateData {
  const PlayerUpdateData({
    required this.gameName,
    required this.tagLine,
    required this.role,
    this.nickname = '',
    this.notes    = '',
  });

  final String gameName;
  final String tagLine;
  final String role;
  final String nickname;
  final String notes;

  Map<String, dynamic> toJson() => {
    'game_name': gameName,
    'tag_line':  tagLine,
    'role':      role,
    'nickname':  nickname,
    'notes':     notes,
  };
}
