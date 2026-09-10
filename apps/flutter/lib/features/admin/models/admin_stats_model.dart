class AdminStatsModel {
  const AdminStatsModel({
    required this.totalUsers,
    required this.activeUsers,
    required this.inactiveUsers,
    required this.totalPlayers,
    required this.totalSnapshots,
    required this.totalMatches,
    required this.tierDistribution,
    required this.regionDistribution,
    required this.topUsers,
  });

  final int                  totalUsers;
  final int                  activeUsers;
  final int                  inactiveUsers;
  final int                  totalPlayers;
  final int                  totalSnapshots;
  final int                  totalMatches;
  final List<TierCount>      tierDistribution;
  final List<RegionCount>    regionDistribution;
  final List<TopUser>        topUsers;

  factory AdminStatsModel.fromJson(Map<String, dynamic> j) => AdminStatsModel(
    totalUsers:         j['total_users']     as int,
    activeUsers:        j['active_users']    as int,
    inactiveUsers:      j['inactive_users']  as int,
    totalPlayers:       j['total_players']   as int,
    totalSnapshots:     j['total_snapshots'] as int,
    totalMatches:       j['total_matches']  as int,
    tierDistribution:   (j['tier_distribution'] as List<dynamic>)
        .map((e) => TierCount.fromJson(e as Map<String, dynamic>)).toList(),
    regionDistribution: (j['region_distribution'] as List<dynamic>)
        .map((e) => RegionCount.fromJson(e as Map<String, dynamic>)).toList(),
    topUsers:           (j['top_users'] as List<dynamic>)
        .map((e) => TopUser.fromJson(e as Map<String, dynamic>)).toList(),
  );
}

class TierCount {
  const TierCount({required this.tier, required this.count});
  final String tier;
  final int    count;
  factory TierCount.fromJson(Map<String, dynamic> j) =>
      TierCount(tier: j['tier'] as String, count: j['count'] as int);
}

class RegionCount {
  const RegionCount({required this.region, required this.count});
  final String region;
  final int    count;
  factory RegionCount.fromJson(Map<String, dynamic> j) =>
      RegionCount(region: j['region'] as String, count: j['count'] as int);
}

class TopUser {
  const TopUser({required this.username, required this.playerCount});
  final String username;
  final int    playerCount;
  factory TopUser.fromJson(Map<String, dynamic> j) =>
      TopUser(username: j['username'] as String, playerCount: j['player_count'] as int);
}
