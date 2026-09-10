import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'core/api/api_client.dart';
import 'core/auth/auth_provider.dart';
import 'core/theme/app_theme.dart';
import 'features/players/providers/snapshot_provider.dart';
import 'screens/dashboard_screen.dart';
import 'screens/login_screen.dart';

SnackBar _authSnackBar({
  required IconData icon,
  required Color iconColor,
  required String message,
  required Color borderColor,
}) => SnackBar(
  content: Row(
    children: [
      Icon(icon, color: iconColor, size: 18),
      const SizedBox(width: 10),
      Text(message, style: const TextStyle(color: kForeground, fontSize: 13)),
    ],
  ),
  backgroundColor: kSurfaceColor,
  shape: RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(8),
    side: BorderSide(color: borderColor),
  ),
  behavior: SnackBarBehavior.floating,
  duration: const Duration(seconds: 3),
  margin: const EdgeInsets.all(16),
);

void main() {
  runApp(const ProviderScope(child: YggApp()));
}

class YggApp extends ConsumerWidget {
  const YggApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'YGG',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      locale: const Locale('en'),
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [Locale('en')],
      home: const _AuthGate(),
    );
  }
}

// ── Enrutador basado en el estado de auth ─────────────────────────────────────

class _AuthGate extends ConsumerStatefulWidget {
  const _AuthGate();

  @override
  ConsumerState<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends ConsumerState<_AuthGate> {
  @override
  void initState() {
    super.initState();
    ApiClient.onUnauthorized = () {
      ref.read(authProvider.notifier).logout();
    };
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AuthState>(authProvider, (prev, next) {
      if (prev?.status == AuthStatus.authenticated &&
          next.status == AuthStatus.unauthenticated) {
        Navigator.of(context).popUntil((route) => route.isFirst);
      }

      if (next.status == AuthStatus.authenticated &&
          prev?.status != AuthStatus.authenticated) {
        resumePendingSnapshotJob(ref);
      }

      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        final messenger = ScaffoldMessenger.of(context);
        messenger.clearSnackBars();

        if (prev?.status != AuthStatus.authenticated &&
            next.status == AuthStatus.authenticated) {
          messenger.showSnackBar(
            _authSnackBar(
              icon: Icons.check_circle_outline_rounded,
              iconColor: kStatGreen,
              message: 'Welcome, ${next.username ?? ''}!',
              borderColor: kStatGreen.withValues(alpha: 0.35),
            ),
          );
        } else if (prev?.status == AuthStatus.authenticated &&
            next.status == AuthStatus.unauthenticated) {
          messenger.showSnackBar(
            _authSnackBar(
              icon: Icons.logout_rounded,
              iconColor: kMuted,
              message: 'Logged out',
              borderColor: kBorderColor,
            ),
          );
        }
      });
    });

    final auth = ref.watch(authProvider);
    return switch (auth.status) {
      AuthStatus.unknown => const _SplashScreen(),
      AuthStatus.authenticated => const DashboardScreen(),
      AuthStatus.unauthenticated => const LoginScreen(),
    };
  }
}

// ── Splash mientras se verifica el token almacenado ───────────────────────────

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SvgPicture.asset('assets/logo/logo.svg', width: 120, height: 90),
            const SizedBox(height: 24),
            const CircularProgressIndicator(color: kPrimary, strokeWidth: 2),
          ],
        ),
      ),
    );
  }
}
