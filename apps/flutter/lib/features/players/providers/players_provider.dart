import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/api/api_client.dart';
import '../models/player.dart';
import '../repositories/player_repository.dart';
import 'match_provider.dart';

// ── Helpers de timestamp para auto-refresh ────────────────────────────────────

const _kRefreshPrefix = 'player_last_refresh_';
const _kAutoRefreshMinutes = 15;

Future<void> savePlayerRefreshTime(int playerId) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setInt(
    '$_kRefreshPrefix$playerId',
    DateTime.now().millisecondsSinceEpoch,
  );
}

Future<bool> shouldAutoRefresh(int playerId) async {
  final prefs = await SharedPreferences.getInstance();
  final lastMs = prefs.getInt('$_kRefreshPrefix$playerId');
  if (lastMs == null) return true;
  final elapsed = DateTime.now().millisecondsSinceEpoch - lastMs;
  return elapsed >= _kAutoRefreshMinutes * 60 * 1000;
}

// ── Repositorio ───────────────────────────────────────────────────────────────

final playerRepositoryProvider = Provider((_) => PlayerRepository());

// ── Notifier principal ────────────────────────────────────────────────────────

class PlayersNotifier extends AutoDisposeAsyncNotifier<List<Player>> {
  PlayerRepository get _repo => ref.read(playerRepositoryProvider);

  @override
  Future<List<Player>> build() => _repo.list();

  Future<void> reload() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_repo.list);
  }

  Future<String?> addPlayer(PlayerCreateData data) async {
    try {
      final newPlayer = await _repo.create(data);
      state = AsyncData([newPlayer, ...state.valueOrNull ?? []]);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }

  Future<String?> updatePlayer(int id, PlayerUpdateData data) async {
    try {
      final updated = await _repo.update(id, data);
      _replaceInList(updated);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }

  Future<String?> refreshPlayer(int id) async {
    try {
      final updated = await _repo.refresh(id);
      _replaceInList(updated);
      await savePlayerRefreshTime(id);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }

  Future<String?> deletePlayer(int id) async {
    try {
      await _repo.delete(id);
      state = AsyncData(
        (state.valueOrNull ?? []).where((p) => p.id != id).toList(),
      );
      ref.invalidate(playerMatchesProvider(id));
      ref.invalidate(playerMatchesCacheProvider(id));
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }

  void _replaceInList(Player updated) {
    final current = state.valueOrNull ?? [];
    state = AsyncData(
      [for (final p in current) p.id == updated.id ? updated : p],
    );
  }
}

final playersProvider =
    AsyncNotifierProvider.autoDispose<PlayersNotifier, List<Player>>(PlayersNotifier.new);