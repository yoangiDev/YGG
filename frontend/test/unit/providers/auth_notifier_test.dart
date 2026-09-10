import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ygg/core/auth/auth_provider.dart';
import 'package:ygg/core/auth/auth_repository.dart';

class MockAuthRepository extends Mock implements AuthRepository {}

// Helper: crea un DioException de respuesta HTTP con el status indicado
DioException _dioError({int statusCode = 500}) => DioException(
  requestOptions: RequestOptions(path: '/auth/login'),
  response: Response(
    requestOptions: RequestOptions(path: '/auth/login'),
    statusCode: statusCode,
    data: {'detail': 'Error del servidor'},
  ),
  type: DioExceptionType.badResponse,
);

const _meOk = {'username': 'ines', 'email': 'ines@test.com', 'role': 'user'};

void main() {
  late MockAuthRepository mockRepo;

  setUp(() => mockRepo = MockAuthRepository());

  ProviderContainer container() {
    final c = ProviderContainer(
      overrides: [authRepositoryProvider.overrideWithValue(mockRepo)],
    );
    addTearDown(c.dispose);
    return c;
  }

  // _checkStoredToken() es async y se lanza en el constructor.
  // Necesitamos bombar el loop de eventos para que termine antes de comprobar.
  Future<void> settle() => Future<void>.delayed(const Duration(milliseconds: 10));

  // ── AuthState ───────────────────────────────────────────────────────────────

  group('AuthState', () {
    test('isAuthenticated es true solo con status authenticated', () {
      expect(const AuthState(status: AuthStatus.authenticated).isAuthenticated,   true);
      expect(const AuthState(status: AuthStatus.unauthenticated).isAuthenticated, false);
      expect(const AuthState(status: AuthStatus.unknown).isAuthenticated,         false);
    });

    test('isAdmin es true solo cuando role es "admin"', () {
      expect(const AuthState(role: 'admin').isAdmin, true);
      expect(const AuthState(role: 'user').isAdmin,  false);
      expect(const AuthState().isAdmin,               false);
    });
  });

  // ── _checkStoredToken ───────────────────────────────────────────────────────

  group('_checkStoredToken (inicio del notifier)', () {
    test('sin token almacenado → unauthenticated', () async {
      SharedPreferences.setMockInitialValues({});

      final c = container();
      c.read(authProvider);
      await settle();

      expect(c.read(authProvider).status, AuthStatus.unauthenticated);
    });

    test('token almacenado + getMe exitoso → authenticated con datos de usuario', () async {
      SharedPreferences.setMockInitialValues({'jwt_token': 'valid_token'});
      when(() => mockRepo.getMe()).thenAnswer((_) async => _meOk);

      final c = container();
      c.read(authProvider);
      await settle();

      final state = c.read(authProvider);
      expect(state.status,   AuthStatus.authenticated);
      expect(state.username, 'ines');
      expect(state.email,    'ines@test.com');
      expect(state.role,     'user');
    });

    test('token almacenado + getMe lanza → unauthenticated (token borrado)', () async {
      SharedPreferences.setMockInitialValues({'jwt_token': 'expired_token'});
      when(() => mockRepo.getMe()).thenThrow(Exception('401'));

      final c = container();
      c.read(authProvider);
      await settle();

      expect(c.read(authProvider).status, AuthStatus.unauthenticated);

      // El token debe haberse eliminado de SharedPreferences
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('jwt_token'), isNull);
    });
  });

  // ── login ───────────────────────────────────────────────────────────────────

  group('login', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('credenciales correctas → authenticated, devuelve true', () async {
      when(() => mockRepo.login(any(), any())).thenAnswer((_) async => 'token');
      when(() => mockRepo.getMe()).thenAnswer((_) async => _meOk);

      final c = container();
      await settle();
      final ok = await c.read(authProvider.notifier).login('ines@test.com', '123456');

      expect(ok, true);
      final state = c.read(authProvider);
      expect(state.status,       AuthStatus.authenticated);
      expect(state.username,     'ines');
      expect(state.role,         'user');
      expect(state.errorMessage, isNull);
    });

    test('DioException 401 → unauthenticated con mensaje de credenciales inválidas', () async {
      when(() => mockRepo.login(any(), any())).thenThrow(_dioError(statusCode: 401));

      final c = container();
      await settle();
      final ok = await c.read(authProvider.notifier).login('ines@test.com', 'wrong');

      expect(ok, false);
      final state = c.read(authProvider);
      expect(state.status,       AuthStatus.unauthenticated);
      expect(state.errorMessage, 'Credenciales inválidas. Vuelve a intentarlo.');
    });

    test('DioException no 401 → unauthenticated con mensaje del backend', () async {
      when(() => mockRepo.login(any(), any())).thenThrow(_dioError(statusCode: 500));

      final c = container();
      await settle();
      final ok = await c.read(authProvider.notifier).login('ines@test.com', '123456');

      expect(ok, false);
      final state = c.read(authProvider);
      expect(state.status,       AuthStatus.unauthenticated);
      expect(state.errorMessage, isNotNull);
    });

    test('excepción genérica → unauthenticated con mensaje de error inesperado', () async {
      when(() => mockRepo.login(any(), any())).thenThrow(Exception('timeout'));

      final c = container();
      await settle();
      final ok = await c.read(authProvider.notifier).login('ines@test.com', '123456');

      expect(ok, false);
      expect(
        c.read(authProvider).errorMessage,
        'Ocurrió un error inesperado. Inténtalo de nuevo.',
      );
    });
  });

  // ── register ────────────────────────────────────────────────────────────────

  group('register', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('registro exitoso → authenticated, devuelve true', () async {
      when(() => mockRepo.register(any(), any(), any())).thenAnswer((_) async => 'token');
      when(() => mockRepo.getMe()).thenAnswer((_) async => _meOk);

      final c = container();
      await settle();
      final ok = await c.read(authProvider.notifier).register('ines@test.com', 'ines', '123456');

      expect(ok, true);
      expect(c.read(authProvider).status, AuthStatus.authenticated);
    });

    test('email duplicado (DioException 400) → unauthenticated con mensaje de error', () async {
      when(() => mockRepo.register(any(), any(), any())).thenThrow(_dioError(statusCode: 400));

      final c = container();
      await settle();
      final ok = await c.read(authProvider.notifier).register('ines@test.com', 'ines', '123456');

      expect(ok, false);
      expect(c.read(authProvider).status,       AuthStatus.unauthenticated);
      expect(c.read(authProvider).errorMessage, isNotNull);
    });
  });

  // ── logout ──────────────────────────────────────────────────────────────────

  group('logout', () {
    test('limpia el estado y llama a repo.logout', () async {
      SharedPreferences.setMockInitialValues({'jwt_token': 'token'});
      when(() => mockRepo.getMe()).thenAnswer((_) async => _meOk);
      when(() => mockRepo.logout()).thenAnswer((_) async {});

      final c = container();
      c.read(authProvider);
      await settle();
      expect(c.read(authProvider).status, AuthStatus.authenticated);

      await c.read(authProvider.notifier).logout();

      expect(c.read(authProvider).status,   AuthStatus.unauthenticated);
      expect(c.read(authProvider).username, isNull);
      verify(() => mockRepo.logout()).called(1);
    });
  });

  // ── clearError ──────────────────────────────────────────────────────────────

  group('clearError', () {
    test('elimina el mensaje de error del estado', () async {
      SharedPreferences.setMockInitialValues({});
      when(() => mockRepo.login(any(), any())).thenThrow(_dioError(statusCode: 401));

      final c = container();
      await settle();
      await c.read(authProvider.notifier).login('x@x.com', 'wrong');
      expect(c.read(authProvider).errorMessage, isNotNull);

      c.read(authProvider.notifier).clearError();

      expect(c.read(authProvider).errorMessage, isNull);
    });
  });
}
