class SnapshotModel {
  const SnapshotModel({
    required this.id,
    required this.playerId,
    required this.dateFrom,
    required this.dateTo,
    required this.description,
    required this.notes,
    this.matchCount = 0,
  });

  final int      id;
  final int      playerId;
  final DateTime dateFrom;
  final DateTime dateTo;
  final String   description;
  final String   notes;
  final int      matchCount;

  factory SnapshotModel.fromJson(Map<String, dynamic> j) => SnapshotModel(
    id:          _readInt(j['id']),
    playerId:    _readInt(j['player_id']),
    dateFrom:    DateTime.parse(j['date_from'] as String).toLocal(),
    dateTo:      DateTime.parse(j['date_to']   as String).toLocal(),
    description: j['description'] as String? ?? '',
    notes:       j['notes']       as String? ?? '',
    matchCount:  _readInt(j['match_count']),
  );

  static int _readInt(dynamic value, [int fallback = 0]) {
    if (value == null) return fallback;
    if (value is int) return value;
    if (value is num) return value.toInt();
    return fallback;
  }
}
