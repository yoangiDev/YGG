import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../../../core/api/api_client.dart';
import '../models/app_user.dart';
import '../models/admin_stats_model.dart';
import '../models/admin_player_model.dart';
import '../repositories/admin_repository.dart';
import '../../players/providers/players_provider.dart';

final adminRepositoryProvider = Provider((_) => AdminRepository());

// ── Notifier de usuarios (admin) ──────────────────────────────────────────────

class AdminUsersNotifier extends AutoDisposeAsyncNotifier<List<AppUser>> {
  AdminRepository get _repo => ref.read(adminRepositoryProvider);

  @override
  Future<List<AppUser>> build() => _repo.listUsers();

  Future<String?> updateRole(int userId, String role) async {
    try {
      final updated = await _repo.updateUserRole(userId, role);
      final current = state.valueOrNull ?? [];
      state = AsyncData([
        for (final u in current) u.id == userId ? updated : u,
      ]);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }

  Future<(String?, int)> deleteInactiveUsers() async {
    try {
      final count = await _repo.deleteInactiveUsers();
      state = AsyncData((state.valueOrNull ?? []).where((u) => u.isActive).toList());
      ref.invalidate(adminStatsProvider);
      return (null, count);
    } on DioException catch (e) {
      return (e.userMessage, 0);
    } catch (e) {
      return (e.toString(), 0);
    }
  }

  Future<String?> deleteUser(int userId) async {
    try {
      await _repo.deleteUser(userId);
      state = AsyncData((state.valueOrNull ?? []).where((u) => u.id != userId).toList());
      ref.invalidate(adminStatsProvider);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }

  Future<String?> toggleActive(int userId) async {
    try {
      final updated = await _repo.toggleUserActive(userId);
      final current = state.valueOrNull ?? [];
      state = AsyncData([
        for (final u in current) u.id == userId ? updated : u,
      ]);
      ref.invalidate(adminStatsProvider);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }

  Future<String?> createUser({
    required String email,
    required String username,
    required String password,
    required String role,
  }) async {
    try {
      final newUser = await _repo.createUser(
        email:    email,
        username: username,
        password: password,
        role:     role,
      );
      state = AsyncData([...state.valueOrNull ?? [], newUser]);
      ref.invalidate(adminStatsProvider);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }
}

final adminUsersProvider =
    AsyncNotifierProvider.autoDispose<AdminUsersNotifier, List<AppUser>>(AdminUsersNotifier.new);

final adminStatsProvider = FutureProvider.autoDispose<AdminStatsModel>((ref) {
  return AdminRepository().getStats();
});

// ── Notifier de jugadores globales (admin) ────────────────────────────────────

class AdminPlayersNotifier extends AutoDisposeAsyncNotifier<List<AdminPlayerModel>> {
  AdminRepository get _repo => ref.read(adminRepositoryProvider);

  @override
  Future<List<AdminPlayerModel>> build() => _repo.listAllPlayers();

  Future<String?> deletePlayer(int playerId) async {
    try {
      await _repo.deleteAdminPlayer(playerId);
      state = AsyncData((state.valueOrNull ?? []).where((p) => p.id != playerId).toList());
      ref.invalidate(playersProvider);
      return null;
    } on DioException catch (e) {
      return e.userMessage;
    } catch (e) {
      return e.toString();
    }
  }
}

final adminPlayersProvider =
    AsyncNotifierProvider.autoDispose<AdminPlayersNotifier, List<AdminPlayerModel>>(
        AdminPlayersNotifier.new);
