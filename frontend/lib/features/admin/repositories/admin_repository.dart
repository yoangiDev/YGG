import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/app_user.dart';
import '../models/admin_stats_model.dart';
import '../models/admin_player_model.dart';

class AdminRepository {
  final _dio = ApiClient.instance.dio;

  Future<List<AppUser>> listUsers() async {
    final response = await _dio.get(Endpoints.adminUsers);
    final data = response.data as List<dynamic>;
    return data.map((e) => AppUser.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<AdminPlayerModel>> listAllPlayers() async {
    final res = await _dio.get(Endpoints.adminPlayers);
    return (res.data as List<dynamic>)
        .map((e) => AdminPlayerModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> deleteAdminPlayer(int playerId) async {
    await _dio.delete(Endpoints.adminPlayer(playerId));
  }

  Future<int> deleteInactiveUsers() async {
    final res = await _dio.delete(Endpoints.adminUsersInactive);
    return (res.data as Map<String, dynamic>)['deleted'] as int;
  }

  Future<void> deleteUser(int userId) async {
    await _dio.delete(Endpoints.adminUser(userId));
  }

  Future<AppUser> toggleUserActive(int userId) async {
    final response = await _dio.patch(Endpoints.adminUserActive(userId));
    return AppUser.fromJson(response.data as Map<String, dynamic>);
  }

  Future<AppUser> updateUserRole(int userId, String role) async {
    final response = await _dio.patch(
      Endpoints.adminUserRole(userId),
      data: {'role': role},
    );
    return AppUser.fromJson(response.data as Map<String, dynamic>);
  }

  Future<AdminStatsModel> getStats() async {
    final res = await _dio.get(Endpoints.adminStats);
    return AdminStatsModel.fromJson(res.data as Map<String, dynamic>);
  }

  Future<AppUser> createUser({
    required String email,
    required String username,
    required String password,
    required String role,
  }) async {
    final response = await _dio.post(
      Endpoints.adminUsers,
      data: {
        'email':    email,
        'username': username,
        'password': password,
        'role':     role,
      },
    );
    return AppUser.fromJson(response.data as Map<String, dynamic>);
  }
}
