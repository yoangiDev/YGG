import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/match_model.dart';
import 'match_provider.dart';
import 'snapshot_provider.dart';
import '../widgets/snapshot_detail/avg_stats_logic.dart';

class AvgStatsRequest {
  const AvgStatsRequest({required this.snapshotId, this.champion});

  final int snapshotId;
  final String? champion;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AvgStatsRequest &&
        other.snapshotId == snapshotId &&
        other.champion == champion;
  }

  @override
  int get hashCode => Object.hash(snapshotId, champion);
}

class AvgStatsPayload {
  const AvgStatsPayload({
    required this.metrics,
    required this.matchCount,
  });

  final List<CalculatedMetric> metrics;
  final int matchCount;
}

final avgStatsPayloadProvider =
    FutureProvider.family<AvgStatsPayload, AvgStatsRequest>((ref, request) async {
  final allMatches = await ref.watch(snapshotMatchesProvider(request.snapshotId).future);
  final dashboard = await ref.watch(snapshotDashboardProvider(request.snapshotId).future);
  final activeRole = dashboard.activeRole;
  final metrics = buildCalculatedMetrics(
    allMatches: allMatches,
    activeRole: activeRole,
    champion: request.champion,
  );

  final matchCount = request.champion == null
      ? allMatches.length
      : allMatches.where((m) => m.champion == request.champion).length;

  return AvgStatsPayload(metrics: metrics, matchCount: matchCount);
});

final filteredSnapshotMatchesProvider =
    FutureProvider.family<List<MatchModel>, AvgStatsRequest>((ref, request) async {
  final allMatches = await ref.watch(snapshotMatchesProvider(request.snapshotId).future);
  if (request.champion == null) return allMatches;
  return allMatches.where((m) => m.champion == request.champion).toList(growable: false);
});
