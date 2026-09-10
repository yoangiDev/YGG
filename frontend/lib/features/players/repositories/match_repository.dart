import 'package:dio/dio.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/match_model.dart';
import '../models/most_played_champion_model.dart';
import '../models/snapshot_stats_model.dart';

class MatchRepository {
  final _dio = ApiClient.instance.dio;

  Future<List<MatchModel>> listForPlayer(int playerId, {bool sync = false}) async {
    try {
      final res = await _dio.get(
        Endpoints.playerMatches(playerId),
        queryParameters: sync ? {'sync': true} : null,
      );
      final data = res.data as List<dynamic>;
      return data.map((e) => MatchModel.fromJson(e as Map<String, dynamic>)).toList();
    } on DioException {
      if (!sync) rethrow;
      // Sync can time out under rate limit — fall back to cached DB read.
      final fallback = await _dio.get(Endpoints.playerMatches(playerId));
      final data = fallback.data as List<dynamic>;
      return data.map((item) => MatchModel.fromJson(item as Map<String, dynamic>)).toList();
    }
  }

  Future<List<MostPlayedChampion>> mostPlayed(int playerId) async {
    final res = await _dio.get(Endpoints.mostPlayed(playerId));
    final data = res.data as List<dynamic>;
    return data.map((e) => MostPlayedChampion.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<MatchModel>> listForSnapshot(int snapshotId) async {
    final res = await _dio.get(Endpoints.snapshotMatches(snapshotId));
    final data = res.data as List<dynamic>;
    return data.map((e) => MatchModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<SnapshotStatsModel> getSnapshotStats(int snapshotId) async {
    final res = await _dio.get(Endpoints.snapshotStats(snapshotId));
    return SnapshotStatsModel.fromJson(res.data as Map<String, dynamic>);
  }
}
