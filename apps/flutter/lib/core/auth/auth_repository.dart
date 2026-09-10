import 'dart:typed_data';
import 'package:dio/dio.dart';
import '../api/api_client.dart';
import '../api/endpoints.dart';

class AuthRepository {
  final _dio = ApiClient.instance.dio;

  Future<String> login(String email, String password) async {
    final response = await _dio.post(
      Endpoints.login,
      data: {'email': email, 'password': password},
    );
    final token = response.data['access_token'] as String;
    await ApiClient.saveToken(token);
    return token;
  }

  Future<String> register(String email, String username, String password) async {
    final response = await _dio.post(
      Endpoints.register,
      data: {'email': email, 'username': username, 'password': password},
    );
    final token = response.data['access_token'] as String;
    await ApiClient.saveToken(token);
    return token;
  }

  Future<Map<String, dynamic>> getMe() async {
    final response = await _dio.get(Endpoints.me);
    return response.data as Map<String, dynamic>;
  }

  Future<void> changePassword(String currentPassword, String newPassword) async {
    await _dio.patch(
      Endpoints.changeMyPassword,
      data: {'current_password': currentPassword, 'new_password': newPassword},
    );
  }

  Future<void> logout() async {
    await ApiClient.clearToken();
  }

  Future<String> uploadAvatar(Uint8List bytes, String filename) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: filename),
    });
    final response = await _dio.patch(
      Endpoints.updateAvatar,
      data: formData,
    );
    return response.data['avatar_url'] as String;
  }
}
