import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/match_model.dart';
import '../models/most_played_champion_model.dart';
import '../models/snapshot_stats_model.dart';
import '../repositories/match_repository.dart';
import 'ddragon_provider.dart';

final matchRepositoryProvider = Provider((_) => MatchRepository());

/// Last successfully loaded matches per player (used when Riot/rate limit fails).
final playerMatchesCacheProvider =
    StateProvider.family<List<MatchModel>, int>((ref, _) => const []);

final playerMatchesProvider =
    FutureProvider.family<List<MatchModel>, int>((ref, playerId) async {
  final repo = ref.watch(matchRepositoryProvider);
  try {
    final matches = await repo.listForPlayer(playerId);
    ref.read(playerMatchesCacheProvider(playerId).notifier).state = matches;
    return matches;
  } catch (_) {
    final cached = ref.read(playerMatchesCacheProvider(playerId));
    if (cached.isNotEmpty) return cached;
    rethrow;
  }
});

List<MostPlayedChampion> mostPlayedFromMatches(
  List<MatchModel> matches,
  String ddragonVersion,
) {
  final counts = <String, int>{};
  final wins = <String, int>{};
  for (final match in matches) {
    counts[match.champion] = (counts[match.champion] ?? 0) + 1;
    if (match.win) {
      wins[match.champion] = (wins[match.champion] ?? 0) + 1;
    }
  }

  final ranked = counts.entries.toList()
    ..sort((a, b) {
      final cmp = b.value.compareTo(a.value);
      if (cmp != 0) return cmp;
      final wrA = (wins[a.key] ?? 0) / a.value;
      final wrB = (wins[b.key] ?? 0) / b.value;
      return wrB.compareTo(wrA);
    });

  return ranked.take(3).map((entry) {
    final games = entry.value;
    final champWins = wins[entry.key] ?? 0;
    return MostPlayedChampion(
      championName: entry.key,
      gamesPlayed: games,
      winRate: games > 0 ? (champWins / games) * 100 : 0.0,
      iconUrl:
          'https://ddragon.leagueoflegends.com/cdn/$ddragonVersion/img/champion/${entry.key}.png',
    );
  }).toList();
}

/// Derived from [playerMatchesProvider] — avoids a second Riot API round-trip.
final mostPlayedProvider =
    FutureProvider.family<List<MostPlayedChampion>, int>((ref, playerId) async {
  final matches = await ref.watch(playerMatchesProvider(playerId).future);
  final version = await ref.watch(ddragonVersionProvider.future);
  return mostPlayedFromMatches(matches, version);
});

final snapshotMatchesProvider =
    FutureProvider.family<List<MatchModel>, int>((ref, snapshotId) async {
  return ref.watch(matchRepositoryProvider).listForSnapshot(snapshotId);
});

final snapshotStatsProvider =
    FutureProvider.family<SnapshotStatsModel, int>((ref, snapshotId) async {
  return ref.watch(matchRepositoryProvider).getSnapshotStats(snapshotId);
});
