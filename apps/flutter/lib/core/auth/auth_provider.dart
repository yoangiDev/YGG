import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../api/api_client.dart';
import 'auth_repository.dart';

// ── Estado de autenticación ──────────────────────────────────────────────────

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthState {
  const AuthState({
    this.status = AuthStatus.unknown,
    this.username,
    this.email,
    this.role,
    this.avatarUrl,
    this.errorMessage,
  });

  final AuthStatus status;
  final String? username;
  final String? email;
  final String? role;
  final String? avatarUrl;
  final String? errorMessage;

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isAdmin => role == 'admin';

  AuthState copyWith({
    AuthStatus? status,
    String? username,
    String? email,
    String? role,
    String? avatarUrl,
    String? errorMessage,
  }) => AuthState(
    status:       status       ?? this.status,
    username:     username     ?? this.username,
    email:        email        ?? this.email,
    role:         role         ?? this.role,
    avatarUrl:    avatarUrl    ?? this.avatarUrl,
    errorMessage: errorMessage,
  );
}

// ── Notifier ─────────────────────────────────────────────────────────────────

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._repo) : super(const AuthState()) {
    _checkStoredToken();
  }

  final AuthRepository _repo;

  Future<void> _checkStoredToken() async {
    final token = await ApiClient.getToken();
    if (token == null) {
      state = state.copyWith(status: AuthStatus.unauthenticated);
      return;
    }
    try {
      final me = await _repo.getMe();
      state = state.copyWith(
        status:    AuthStatus.authenticated,
        username:  me['username']   as String?,
        email:     me['email']      as String?,
        role:      me['role']       as String?,
        avatarUrl: me['avatar_url'] as String?,
      );
    } catch (_) {
      await ApiClient.clearToken();
      state = state.copyWith(status: AuthStatus.unauthenticated);
    }
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(status: AuthStatus.unknown, errorMessage: null);
    try {
      await _repo.login(email, password);
      final me = await _repo.getMe();
      state = state.copyWith(
        status:    AuthStatus.authenticated,
        username:  me['username']   as String?,
        email:     me['email']      as String?,
        role:      me['role']       as String?,
        avatarUrl: me['avatar_url'] as String?,
      );
      return true;
    } on DioException catch (e) {
      final msg = e.response?.statusCode == 401
          ? 'Invalid credentials. Please try again.'
          : e.userMessage;
      state = state.copyWith(status: AuthStatus.unauthenticated, errorMessage: msg);
      return false;
    } catch (_) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        errorMessage: 'An unexpected error occurred. Please try again.',
      );
      return false;
    }
  }

  Future<bool> register(String email, String username, String password) async {
    state = state.copyWith(status: AuthStatus.unknown, errorMessage: null);
    try {
      await _repo.register(email, username, password);
      final me = await _repo.getMe();
      state = state.copyWith(
        status:    AuthStatus.authenticated,
        username:  me['username']   as String?,
        email:     me['email']      as String?,
        role:      me['role']       as String?,
        avatarUrl: me['avatar_url'] as String?,
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        errorMessage: e.userMessage,
      );
      return false;
    } catch (_) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        errorMessage: 'An unexpected error occurred. Please try again.',
      );
      return false;
    }
  }

  Future<void> logout() async {
    await _repo.logout();
    state = const AuthState(status: AuthStatus.unauthenticated);
  }

  void clearError() {
    state = state.copyWith(errorMessage: null);
  }

  Future<void> uploadAvatar(Uint8List bytes, String filename) async {
    final url = await _repo.uploadAvatar(bytes, filename);
    state = state.copyWith(avatarUrl: url);
  }

}

// ── Providers ────────────────────────────────────────────────────────────────

final authRepositoryProvider = Provider((_) => AuthRepository());

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(ref.read(authRepositoryProvider)),
);
