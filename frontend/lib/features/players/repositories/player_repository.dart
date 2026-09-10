import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/player.dart';

class PlayerRepository {
  final _dio = ApiClient.instance.dio;

  Future<List<Player>> list() async {
    final response = await _dio.get(Endpoints.players);
    final data = response.data as List<dynamic>;
    return data.map((e) => Player.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Player> create(PlayerCreateData data) async {
    final response = await _dio.post(Endpoints.players, data: data.toJson());
    return Player.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Player> update(int id, PlayerUpdateData data) async {
    final response = await _dio.put(Endpoints.player(id), data: data.toJson());
    return Player.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Player> refresh(int id) async {
    final response = await _dio.post(Endpoints.refreshPlayer(id));
    return Player.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> delete(int id) async {
    await _dio.delete(Endpoints.player(id));
  }
}
