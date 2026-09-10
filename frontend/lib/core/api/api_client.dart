import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'endpoints.dart';

const _tokenKey = 'jwt_token';

class ApiClient {
  // Callback invocado cuando el servidor devuelve 401 (token expirado/inválido).
  // Se asigna desde _AuthGate al inicializar la sesión.
  static void Function()? onUnauthorized;
  ApiClient._() {
    _dio = Dio(
      BaseOptions(
        baseUrl: Endpoints.baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 90),
        headers: {'Content-Type': 'application/json'},
      ),
    );
    _dio.interceptors.add(_JwtInterceptor());
  }

  static final ApiClient instance = ApiClient._();
  late final Dio _dio;

  Dio get dio => _dio;

  // ── Helpers de respuesta ───────────────────────────────────────────────────

  static Future<void> saveToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  static Future<void> clearToken() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }
}

// ── Interceptor JWT ──────────────────────────────────────────────────────────

class _JwtInterceptor extends Interceptor {
  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await ApiClient.getToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    // Token expirado o inválido → cerrar sesión automáticamente.
    // Se excluyen los endpoints de auth para que los errores de credenciales
    // se propaguen normalmente y se muestren en el formulario.
    if (err.response?.statusCode == 401) {
      final path = err.requestOptions.path;
      if (path != Endpoints.login && path != Endpoints.register) {
        ApiClient.onUnauthorized?.call();
      }
      handler.next(err);
      return;
    }
    // Propagar el error con el mensaje del backend si está disponible
    final data = err.response?.data;
    final detail = data is Map ? data['detail'] : null;
    if (detail != null && detail is String) {
      handler.next(
        DioException(
          requestOptions: err.requestOptions,
          response: err.response,
          type: err.type,
          error: detail,
        ),
      );
      return;
    }
    handler.next(err);
  }
}

// ── Extensión para extraer mensajes de error legibles ────────────────────────

extension DioErrorMessage on DioException {
  String get userMessage {
    if (error is String) return error as String;
    switch (type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'The server is taking too long to respond. Please try again.';
      case DioExceptionType.connectionError:
        return 'Cannot connect to the server. Make sure it is running.';
      case DioExceptionType.cancel:
        return 'The request was cancelled.';
      default:
        final data = response?.data;
        if (data is Map) {
          final detail = data['detail'];
          if (detail is String) return detail;
          if (response?.statusCode == 422) {
            return 'The submitted data is invalid. Please check your fields.';
          }
        }
        return 'An unexpected error occurred. Please try again.';
    }
  }
}
