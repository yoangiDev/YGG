import 'dart:math' as math;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../../core/theme/app_theme.dart';
import '../../../providers/ddragon_provider.dart';
import 'heatmap_math.dart';
import 'heatmap_painter.dart';

class CompactHeatmapView extends ConsumerWidget {
  const CompactHeatmapView({
    super.key,
    required this.points,
    required this.accentColor,
    required this.gameCount,
    required this.label,
    required this.hint,
    this.emptyLabel = 'No locations for this filter',
  });

  final List<HeatmapPoint> points;
  final Color accentColor;
  final int gameCount;
  final String label;
  final String hint;
  final String emptyLabel;

  static double mapSizeForConstraints(BoxConstraints constraints) {
    final w = constraints.maxWidth.isFinite ? constraints.maxWidth : 480.0;
    return math.min(w, 480.0).clamp(240.0, 480.0);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mapUrlAsync = ref.watch(ddragonMapUrlProvider);
    final hasData = points.isNotEmpty;

    return LayoutBuilder(
      builder: (context, constraints) {
        final mapSize = mapSizeForConstraints(constraints);
        final perGame = gameCount > 0 ? (points.length / gameCount) : 0.0;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // ── MAP ──────────────────────────────────────────────────────────
            Center(
              child: Container(
                width: mapSize,
                height: mapSize,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: accentColor.withValues(alpha: 0.35),
                    width: 1.5,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: accentColor.withValues(alpha: 0.20),
                      blurRadius: 28,
                      spreadRadius: 0,
                    ),
                    BoxShadow(
                      color: accentColor.withValues(alpha: 0.07),
                      blurRadius: 8,
                      spreadRadius: -2,
                    ),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(11),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      // Map background
                      mapUrlAsync.when(
                        loading: () => Container(color: kSurface2),
                        error: (e, _) => Container(
                          color: kSurface2,
                          alignment: Alignment.center,
                          child: const Icon(Icons.map_outlined, color: kMuted, size: 32),
                        ),
                        data: (url) => CachedNetworkImage(
                          imageUrl: url,
                          fit: BoxFit.cover,
                          placeholder: (context, url) => Container(color: kSurface2),
                          errorWidget: (context, url, error) => Container(color: kSurface2),
                        ),
                      ),
                      // Subtle dim so heatmap pops
                      CustomPaint(painter: MapDimOverlayPainter()),
                      // Edge vignette for depth
                      CustomPaint(painter: MapVignettePainter()),
                      // Heatmap blobs
                      if (hasData)
                        CustomPaint(
                          painter: HeatmapDotPainter(
                            points: points,
                            color: accentColor,
                            dotRadius: mapSize * 0.068,
                            peakOpacity: 0.75,
                          ),
                        ),
                      // Empty state
                      if (!hasData)
                        Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.location_off_outlined,
                                color: kMuted.withValues(alpha: 0.55),
                                size: 32,
                              ),
                              const SizedBox(height: 10),
                              Text(
                                emptyLabel,
                                style: const TextStyle(fontSize: 11, color: kMuted),
                                textAlign: TextAlign.center,
                              ),
                            ],
                          ),
                        ),
                      // Label badge — top left
                      Positioned(
                        top: 10,
                        left: 12,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0A0E14).withValues(alpha: 0.80),
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(
                              color: accentColor.withValues(alpha: 0.45),
                            ),
                          ),
                          child: Text(
                            label.toUpperCase(),
                            style: TextStyle(
                              fontSize: 8,
                              fontWeight: FontWeight.w700,
                              color: accentColor,
                              letterSpacing: 1.6,
                            ),
                          ),
                        ),
                      ),
                      // Game count badge — top right
                      Positioned(
                        top: 10,
                        right: 12,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0A0E14).withValues(alpha: 0.80),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '$gameCount games',
                            style: const TextStyle(
                              fontSize: 8,
                              color: kMuted,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            if (hasData) ...[
              const SizedBox(height: 16),

              // ── STATS ROW ─────────────────────────────────────────────────
              Center(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _StatChip(
                      label: 'LOCATIONS',
                      value: '${points.length}',
                      accentColor: accentColor,
                    ),
                    const SizedBox(width: 10),
                    _StatChip(
                      label: 'GAMES',
                      value: '$gameCount',
                      accentColor: accentColor,
                    ),
                    const SizedBox(width: 10),
                    _StatChip(
                      label: 'PER GAME',
                      value: perGame.toStringAsFixed(1),
                      accentColor: accentColor,
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 12),

              // ── DENSITY LEGEND ────────────────────────────────────────────
              Center(child: _GradientLegend(accentColor: accentColor)),
            ],

            const SizedBox(height: 10),

            // ── HINT ──────────────────────────────────────────────────────────
            Text(
              hint,
              style: const TextStyle(fontSize: 10, color: kMuted, height: 1.4),
              textAlign: TextAlign.center,
            ),
          ],
        );
      },
    );
  }
}

// ── Stat chip ──────────────────────────────────────────────────────────────────

class _StatChip extends StatelessWidget {
  const _StatChip({
    required this.label,
    required this.value,
    required this.accentColor,
  });

  final String label;
  final String value;
  final Color accentColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 82),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: accentColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: accentColor.withValues(alpha: 0.25)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            value,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: accentColor,
              height: 1.1,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            style: const TextStyle(
              fontSize: 8,
              color: kMuted,
              letterSpacing: 1.2,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Gradient legend ────────────────────────────────────────────────────────────

class _GradientLegend extends StatelessWidget {
  const _GradientLegend({required this.accentColor});

  final Color accentColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text('Low density', style: TextStyle(fontSize: 9, color: kMuted)),
        const SizedBox(width: 8),
        Container(
          width: 96,
          height: 6,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(3),
            gradient: LinearGradient(
              colors: [
                accentColor.withValues(alpha: 0.1),
                accentColor.withValues(alpha: 0.45),
                accentColor.withValues(alpha: 0.88),
              ],
            ),
          ),
        ),
        const SizedBox(width: 8),
        const Text('High density', style: TextStyle(fontSize: 9, color: kMuted)),
      ],
    );
  }
}
