import 'package:flutter/material.dart';

// ── Shimmer wrapper ───────────────────────────────────────────────────────────
// Wrap any subtree of ShimmerBox widgets with this to get the animated sweep.

class Shimmer extends StatefulWidget {
  const Shimmer({super.key, required this.child});
  final Widget child;

  @override
  State<Shimmer> createState() => _ShimmerState();
}

class _ShimmerState extends State<Shimmer> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, _) => ShaderMask(
        blendMode: BlendMode.srcATop,
        shaderCallback: (bounds) {
          final v = _ctrl.value;
          return LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: const [
              Color(0xFF1C1729),
              Color(0xFF3A1F6E),
              Color(0xFF1C1729),
            ],
            stops: [
              (v - 0.35).clamp(0.0, 1.0),
              v.clamp(0.0, 1.0),
              (v + 0.35).clamp(0.0, 1.0),
            ],
          ).createShader(bounds);
        },
        child: widget.child,
      ),
    );
  }
}

// ── ShimmerBox ────────────────────────────────────────────────────────────────
// Plain coloured box — place inside a Shimmer to animate it.

class ShimmerBox extends StatelessWidget {
  const ShimmerBox({
    super.key,
    this.width,
    required this.height,
    this.radius = 4,
  });

  final double? width;
  final double  height;
  final double  radius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: const Color(0xFF2A1F3D),
        borderRadius: BorderRadius.circular(radius),
      ),
    );
  }
}
