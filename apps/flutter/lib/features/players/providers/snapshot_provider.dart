import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/snapshot_model.dart';
import '../models/snapshot_dashboard_model.dart';
import '../repositories/snapshot_repository.dart';
import 'match_provider.dart';
import 'players_provider.dart';

// Mapa persistido: playerId (string) → jobId
const _kActiveJobsKey = 'snapshot_active_jobs';

Future<Map<String, String>> _readActiveJobs() async {
  final prefs = await SharedPreferences.getInstance();
  final json  = prefs.getString(_kActiveJobsKey);
  if (json == null) return {};
  return Map<String, String>.from(jsonDecode(json) as Map);
}

Future<void> _writeActiveJobs(Map<String, String> jobs) async {
  final prefs = await SharedPreferences.getInstance();
  if (jobs.isEmpty) {
    await prefs.remove(_kActiveJobsKey);
  } else {
    await prefs.setString(_kActiveJobsKey, jsonEncode(jobs));
  }
}

final snapshotRepositoryProvider = Provider((_) => SnapshotRepository());

// Progreso de creación (0-100) por playerId — sin autoDispose para sobrevivir navegación
final snapshotCreationProgressProvider =
    StateProvider.family<int, int>((ref, _) => 0);

// Flag de creación en curso — sin autoDispose por el mismo motivo
final snapshotCreatingProvider =
    StateProvider.family<bool, int>((ref, _) => false);

// Notificación global al terminar — la escucha DashboardScreen
class SnapshotNotification {
  const SnapshotNotification({required this.message, required this.isSuccess});
  final String message;
  final bool   isSuccess;
}

final snapshotNotificationProvider = StateProvider<SnapshotNotification?>((ref) => null);

// playerIds con job activo en este momento
final snapshotActivePlayerIdsProvider = StateProvider<Set<int>>((ref) => {});

class PlayerSnapshotsNotifier
    extends FamilyAsyncNotifier<List<SnapshotModel>, int> {
  SnapshotRepository get _repo => ref.read(snapshotRepositoryProvider);

  @override
  Future<List<SnapshotModel>> build(int playerId) =>
      _repo.listForPlayer(playerId);

  // Reanuda un job persistido (llamado desde main al arrancar la app)
  Future<void> resumeJob(String jobId) => _pollJob(jobId, arg);

  Future<String?> create({
    required int      playerId,
    required DateTime dateFrom,
    required DateTime dateTo,
    String            description = '',
  }) async {
    ref.read(snapshotCreationProgressProvider(playerId).notifier).state = 0;
    ref.read(snapshotCreatingProvider(playerId).notifier).state = true;

    try {
      final endOfDay = DateTime(dateTo.year, dateTo.month, dateTo.day, 23, 59, 59);
      final jobId = await _repo.create(
        playerId:    playerId,
        dateFrom:    dateFrom.millisecondsSinceEpoch ~/ 1000,
        dateTo:      endOfDay.millisecondsSinceEpoch ~/ 1000,
        description: description,
      );

      // Persiste el job en el mapa para que sobreviva reinicios
      final jobs = await _readActiveJobs();
      jobs['$playerId'] = jobId;
      await _writeActiveJobs(jobs);

      return await _pollJob(jobId, playerId);
    } catch (e) {
      ref.read(snapshotCreatingProvider(playerId).notifier).state = false;
      final result = e.toString();
      _notifyCompletion(playerId, result);
      return result;
    }
  }

  Future<String?> _pollJob(String jobId, int playerId) async {
    ref.read(snapshotCreatingProvider(playerId).notifier).state = true;
    ref.read(snapshotActivePlayerIdsProvider.notifier).update((s) => {...s, playerId});
    String? result;
    try {
      SnapshotJobStatus status;
      do {
        await Future<void>.delayed(const Duration(seconds: 2));
        status = await _repo.jobStatus(jobId);
        ref.read(snapshotCreationProgressProvider(playerId).notifier).state = status.progress;
      } while (status.status == 'processing');

      if (status.status == 'error') {
        result = status.error ?? 'Failed to create snapshot.';
        return result;
      }

      final updated = await _repo.listForPlayer(playerId);
      state = AsyncData(updated);
      ref.invalidate(playerMatchesProvider(playerId));
      return null;
    } catch (e) {
      result = e.toString();
      return result;
    } finally {
      ref.read(snapshotCreatingProvider(playerId).notifier).state = false;
      ref.read(snapshotActivePlayerIdsProvider.notifier).update((s) => {...s}..remove(playerId));
      final jobs = await _readActiveJobs();
      jobs.remove('$playerId');
      await _writeActiveJobs(jobs);
      _notifyCompletion(playerId, result);
    }
  }

  void _notifyCompletion(int playerId, String? error) {
    final players = ref.read(playersProvider).valueOrNull ?? [];
    final player  = players.where((p) => p.id == playerId).firstOrNull;
    final name    = player != null
        ? (player.nickname.isNotEmpty ? player.nickname : player.gameName)
        : 'Player #$playerId';

    ref.read(snapshotNotificationProvider.notifier).state = SnapshotNotification(
      message:   error == null
          ? 'Snapshot for $name created successfully.'
          : 'Snapshot error for $name: $error',
      isSuccess: error == null,
    );
  }

  Future<String?> delete(int snapshotId) async {
    try {
      await _repo.delete(snapshotId);
      final current = state.valueOrNull ?? [];
      state = AsyncData(current.where((s) => s.id != snapshotId).toList());
      ref.invalidate(snapshotDashboardProvider(snapshotId));
      ref.invalidate(snapshotMatchesProvider(snapshotId));
      ref.invalidate(snapshotStatsProvider(snapshotId));
      return null;
    } catch (e) {
      return e.toString();
    }
  }
}

final snapshotsProvider = AsyncNotifierProvider.family<
    PlayerSnapshotsNotifier, List<SnapshotModel>, int>(
  PlayerSnapshotsNotifier.new,
);

/// Llama a esto al arrancar la app (cuando el usuario está autenticado)
/// para reanudar en background todos los jobs que quedaron a medias.
Future<void> resumePendingSnapshotJob(WidgetRef ref) async {
  final jobs = await _readActiveJobs();
  for (final entry in jobs.entries) {
    final playerId = int.tryParse(entry.key);
    final jobId    = entry.value;
    if (playerId != null) {
      unawaited(ref.read(snapshotsProvider(playerId).notifier).resumeJob(jobId));
    }
  }
}

final snapshotDashboardProvider =
    FutureProvider.family<SnapshotDashboardModel, int>((ref, snapshotId) async {
  return ref.read(snapshotRepositoryProvider).getDashboard(snapshotId);
});
