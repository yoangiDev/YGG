import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../../core/theme/app_theme.dart';

class LoginBrandingPanel extends StatelessWidget {
  const LoginBrandingPanel({super.key, required this.glowAnim});
  final Animation<double> glowAnim;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color(0xFF2A1650),
                kBgColor,
                Color(0xFF1A0D36),
              ],
              stops: [0.0, 0.50, 1.0],
            ),
          ),
        ),

        const CustomPaint(painter: _ParticlesPainter()),

        AnimatedBuilder(
          animation: glowAnim,
          builder: (_, child) =>
              CustomPaint(painter: _AtmosphericGlowPainter(glowAnim.value)),
        ),

        Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: 260,
                  height: 140,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(999),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFFAA44FF).withValues(alpha: 0.75),
                        blurRadius: 55,
                        spreadRadius: 12,
                      ),
                      BoxShadow(
                        color: const Color(0xFF8822EE).withValues(alpha: 0.40),
                        blurRadius: 100,
                        spreadRadius: 30,
                      ),
                    ],
                  ),
                ),
                SvgPicture.asset(
                  'assets/logo/logo.svg',
                  width: 280,
                  height: 280,
                ),
              ],
            ),
            const SizedBox(height: 60),

            ShaderMask(
              shaderCallback: (bounds) => const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [kPrimaryLight, kPrimary],
              ).createShader(bounds),
              child: const Text(
                'YGG',
                style: TextStyle(
                  fontSize: 56,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 16,
                  color: Colors.white,
                  height: 1.0,
                ),
              ),
            ),
            const SizedBox(height: 16),

            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _gradientLine(leftToRight: false),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 14),
                  child: Text(
                    'PRO SCOUTING',
                    style: TextStyle(
                      fontSize: 10,
                      letterSpacing: 5,
                      color: kMuted,
                    ),
                  ),
                ),
                _gradientLine(leftToRight: true),
              ],
            ),
          ],
        ),

        const Positioned(
          bottom: 24,
          left: 0,
          right: 0,
          child: Text(
            'v1.0.0',
            textAlign: TextAlign.center,
            style: TextStyle(color: Color(0xFF2A2440), fontSize: 11),
          ),
        ),
      ],
    );
  }

  Widget _gradientLine({required bool leftToRight}) => Container(
    width: 48,
    height: 1,
    decoration: BoxDecoration(
      gradient: LinearGradient(
        colors: leftToRight
            ? [kPrimary.withValues(alpha: 0.5), Colors.transparent]
            : [Colors.transparent, kPrimary.withValues(alpha: 0.5)],
      ),
    ),
  );
}

class _ParticlesPainter extends CustomPainter {
  const _ParticlesPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final rng = math.Random(42);

    for (int i = 0; i < 90; i++) {
      final x = rng.nextDouble() * size.width;
      final y = rng.nextDouble() * size.height;
      final radius = 0.7 + rng.nextDouble() * 2.0;
      final alpha = 0.04 + rng.nextDouble() * 0.10;
      final bright = rng.nextDouble() > 0.72;

      canvas.drawCircle(
        Offset(x, y),
        radius,
        Paint()
          ..color = bright
              ? kPrimaryLight.withValues(alpha: alpha * 2.0)
              : kPrimary.withValues(alpha: alpha),
      );
    }
  }

  @override
  bool shouldRepaint(_ParticlesPainter old) => false;
}

class _AtmosphericGlowPainter extends CustomPainter {
  const _AtmosphericGlowPainter(this.t);
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    _glow(
      canvas,
      Offset(size.width * 0.28, size.height * 0.35),
      kPrimary.withValues(alpha: 0.12 + t * 0.08),
      220,
    );
    _glow(
      canvas,
      Offset(size.width * 0.80, size.height * 0.15),
      kPrimaryDim.withValues(alpha: 0.07 + t * 0.05),
      170,
    );
    _glow(
      canvas,
      Offset(size.width * 0.10, size.height * 0.80),
      kPrimary.withValues(alpha: 0.06 + t * 0.04),
      150,
    );
    _glow(
      canvas,
      Offset(size.width * 0.72, size.height * 0.80),
      kPrimaryLight.withValues(alpha: 0.03 + t * 0.03),
      110,
    );
  }

  void _glow(Canvas canvas, Offset center, Color color, double radius) {
    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..shader = RadialGradient(
          colors: [color, Colors.transparent],
        ).createShader(Rect.fromCircle(center: center, radius: radius)),
    );
  }

  @override
  bool shouldRepaint(_AtmosphericGlowPainter old) => old.t != t;
}
