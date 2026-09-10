import 'dart:math' as math;
import 'dart:ui';

class HeatmapPoint {
  const HeatmapPoint(this.x, this.y);
  final double x;
  final double y;
}

List<double> buildHeatmapGrid(
  List<HeatmapPoint> points, {
  int gridSize = 40,
  double kernelRadius = 0.06,
}) {
  final grid = List<double>.filled(gridSize * gridSize, 0);
  if (points.isEmpty) return grid;

  final radiusSq = kernelRadius * kernelRadius;

  for (final p in points) {
    final cx = p.x.clamp(0.0, 1.0);
    final cy = p.y.clamp(0.0, 1.0);

    final minGx = math.max(0, ((cx - kernelRadius) * gridSize).floor());
    final maxGx = math.min(gridSize - 1, ((cx + kernelRadius) * gridSize).ceil());
    final minGy = math.max(0, ((cy - kernelRadius) * gridSize).floor());
    final maxGy = math.min(gridSize - 1, ((cy + kernelRadius) * gridSize).ceil());

    for (var gy = minGy; gy <= maxGy; gy++) {
      for (var gx = minGx; gx <= maxGx; gx++) {
        final px = (gx + 0.5) / gridSize;
        final py = (gy + 0.5) / gridSize;
        final dx = px - cx;
        final dy = py - cy;
        final distSq = dx * dx + dy * dy;
        if (distSq <= radiusSq) {
          final weight = math.exp(-distSq / (radiusSq * 0.35));
          grid[gy * gridSize + gx] += weight;
        }
      }
    }
  }

  final maxVal = grid.reduce(math.max);
  if (maxVal <= 0) return grid;
  return grid.map((v) => v / maxVal).toList();
}

Color heatmapColor(double intensity, Color low, Color high) {
  final t = intensity.clamp(0.0, 1.0);
  return Color.lerp(low, high, t) ?? low;
}
