import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'heatmap_math.dart';

/// Soft radial blobs — reads better than blocky grid cells on a busy map.
class HeatmapDotPainter extends CustomPainter {
  HeatmapDotPainter({
    required this.points,
    required this.color,
    this.dotRadius = 11,
    this.peakOpacity = 0.55,
  });

  final List<HeatmapPoint> points;
  final Color color;
  final double dotRadius;
  final double peakOpacity;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;

    for (final p in points) {
      final cx = p.x.clamp(0.0, 1.0) * size.width;
      final cy = p.y.clamp(0.0, 1.0) * size.height;
      final center = Offset(cx, cy);
      final radius = dotRadius;

      final paint = Paint()
        ..shader = ui.Gradient.radial(
          center,
          radius,
          [
            color.withValues(alpha: peakOpacity),
            color.withValues(alpha: peakOpacity * 0.38),
            color.withValues(alpha: 0),
          ],
          [0.0, 0.42, 1.0],
        );
      canvas.drawCircle(center, radius, paint);
    }
  }

  @override
  bool shouldRepaint(covariant HeatmapDotPainter oldDelegate) {
    return oldDelegate.points != points || oldDelegate.color != color;
  }
}

/// Lightened dim so the map terrain is still readable under the heatmap.
class MapDimOverlayPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()..color = const Color(0x550A0E14),
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Radial vignette — edges fade to dark, keeping focus on the centre.
class MapVignettePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..shader = ui.Gradient.radial(
        Offset(size.width * 0.5, size.height * 0.5),
        size.width * 0.72,
        [
          Colors.transparent,
          const Color(0x990A0E14),
        ],
        [0.42, 1.0],
      );
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
