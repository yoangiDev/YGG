import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/match_model.dart';
import '../../providers/match_provider.dart';
import 'chart_shared_widgets.dart';

// ── Glow dot painter ──────────────────────────────────────────────────────────

class _GlowDotPainter extends FlDotPainter {
  const _GlowDotPainter({
    required this.radius,
    required this.coreColor,
    required this.glowColor,
    this.dimmed = false,
  });

  final double radius;
  final Color  coreColor;
  final Color  glowColor;
  final bool   dimmed;

  @override
  Color get mainColor => coreColor;

  @override
  List<Object?> get props => [radius, coreColor, glowColor, dimmed];

  @override
  void draw(Canvas canvas, FlSpot spot, Offset center) {
    final alpha = dimmed ? 0.35 : 1.0;

    // Halo exterior difuso
    for (final (r, a) in [
      (radius * 3.0, 0.05),
      (radius * 2.4, 0.12),
      (radius * 1.9, 0.24),
      (radius * 1.5, 0.42),
      (radius * 1.2, 0.60),
    ]) {
      canvas.drawCircle(
        center,
        r,
        Paint()
          ..color     = glowColor.withValues(alpha: a * alpha)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
      );
    }

    // Núcleo brillante
    canvas.drawCircle(
      center,
      radius,
      Paint()..color = coreColor.withValues(alpha: alpha),
    );
    // Destello central blanco puro
    canvas.drawCircle(
      center,
      radius * 0.45,
      Paint()..color = Colors.white.withValues(alpha: 0.85 * alpha),
    );
  }

  @override
  Size getSize(FlSpot spot) => Size(radius * 2, radius * 2);

  @override
  FlDotPainter lerp(FlDotPainter a, FlDotPainter b, double t) => b;
}

class DamageGoldChart extends ConsumerStatefulWidget {
  const DamageGoldChart({
    super.key,
    required this.snapshotId,
    this.champion,
  });

  final int     snapshotId;
  final String? champion;

  @override
  ConsumerState<DamageGoldChart> createState() => _DamageGoldChartState();
}

class _DamageGoldChartState extends ConsumerState<DamageGoldChart> {
  int? _hoveredIndex; // index dentro de matches[], null = ninguno

  List<MatchModel> _filter(List<MatchModel> all) =>
      (widget.champion != null
          ? all.where((m) => m.champion == widget.champion)
          : all)
          .where((m) => m.goldShare > 0 || m.damageShare > 0)
          .toList();

  @override
  Widget build(BuildContext context) {
    final matchesAsync = ref.watch(snapshotMatchesProvider(widget.snapshotId));

    final narrow = MediaQuery.of(context).size.width < 600;
    return ChartCard(
      title:    'Damage vs Gold Efficiency',
      subtitle: 'Gold Share % (X) · Damage Share % (Y) · Diagonal = perfect equilibrium',
      onFullscreen: narrow && !chartIsInFullscreen(context)
          ? () => FullscreenChartScreen.push(
                context,
                DamageGoldChart(snapshotId: widget.snapshotId, champion: widget.champion),
              )
          : null,
      headerTrailing: Wrap(
        spacing:    10,
        runSpacing: 4,
        children: const [
          _QuadLegendItem(color: kStatGold,  label: 'Optimal'),
          _QuadLegendItem(color: kStatBlue,  label: 'Efficient'),
          _QuadLegendItem(color: kStatRed,   label: 'Inefficient'),
          _QuadLegendItem(color: kStatGray,  label: 'Low impact'),
        ],
      ),
      child: matchesAsync.when(
        loading: () => const SizedBox(
          height: 200,
          child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
        ),
        error: (e, _) => const SizedBox(
          height: 200,
          child: Center(child: Text('Error loading data', style: TextStyle(color: kMuted, fontSize: 12))),
        ),
        data: (all) => _buildContent(_filter(all)),
      ),
    );
  }

  Widget _buildContent(List<MatchModel> matches) {
    if (matches.length < 2) {
      return const SizedBox(
        height: 140,
        child: Center(child: Text('Not enough data', style: TextStyle(color: kMuted, fontSize: 12))),
      );
    }

    // ── Aggregates ────────────────────────────────────────────────────────────
    final goldVals   = matches.map((m) => m.goldShare).toList();
    final damageVals = matches.map((m) => m.damageShare).toList();

    final avgGold   = goldVals.reduce((a, b) => a + b)   / matches.length;
    final avgDamage = damageVals.reduce((a, b) => a + b) / matches.length;

    final consistency = matches
            .map((m) {
              final dx = m.goldShare   - avgGold;
              final dy = m.damageShare - avgDamage;
              return math.sqrt(dx * dx + dy * dy);
            })
            .reduce((a, b) => a + b) /
        matches.length;

    // ── Axis bounds con padding ───────────────────────────────────────────────
    const pad = 5.0;
    final minX = (goldVals.reduce(math.min)   - pad).clamp(0.0, 100.0);
    final maxX = (goldVals.reduce(math.max)   + pad).clamp(0.0, 100.0);
    final minY = (damageVals.reduce(math.min) - pad).clamp(0.0, 100.0);
    final maxY = (damageVals.reduce(math.max) + pad).clamp(0.0, 100.0);

    // Diagonal Y=X recortada al área visible
    final diagStart = math.max(minX, minY);
    final diagEnd   = math.min(maxX, maxY);

    // ── Efficiency ────────────────────────────────────────────────────────────
    final eff      = avgGold > 0 ? avgDamage / avgGold : 0.0;
    final effColor = eff >= 1.1
        ? kStatGold
        : eff >= 0.95
            ? kStatGreen
            : eff >= 0.80
                ? kStatBlue
                : kStatGray;

    final consistencyColor = consistency <= 3
        ? kStatGold
        : consistency <= 6 ? kStatBlue : kStatGray;
    final consistencyLabel = consistency <= 3 ? 'HIGH'
        : consistency <= 6 ? 'MED' : 'LOW';

    // ── Dot sizing (igual que las otras gráficas) ─────────────────────────────
    final baseRadius = matches.length > 80 ? 2.0
        : matches.length > 40 ? 3.0
        : 4.5;
    final baseStroke = matches.length > 40 ? 0.8 : 1.5;

    final hasHover = _hoveredIndex != null;

    // ── Bar index map ─────────────────────────────────────────────────────────
    // 0-3      → fondos de cuadrante (siempre 4 barras)
    // 4        → diagonal Y=X (si existe)
    // 5..n+4   → vectores radiales
    // n+5      → dots de partida
    // n+6      → centro de masa
    const quadBars     = 4;
    final hasDiag      = diagStart <= diagEnd;
    final diagOffset   = hasDiag ? 1 : 0;
    final matchBarIdx  = quadBars + diagOffset + matches.length;
    final centerBarIdx = quadBars + diagOffset + matches.length + 1;

    final lineBarsData = <LineChartBarData>[

      // ── Fondos de cuadrante ───────────────────────────────────────────────
      // Arriba-izquierda: poco oro, mucho daño → eficiente (azul)
      LineChartBarData(
        spots:    [FlSpot(minX, avgDamage), FlSpot(avgGold, avgDamage)],
        color:    Colors.transparent, barWidth: 0,
        dotData:  const FlDotData(show: false),
        aboveBarData: BarAreaData(show: true, color: kStatBlue.withValues(alpha: 0.07)),
      ),
      // Arriba-derecha: mucho oro, mucho daño → óptimo (dorado)
      LineChartBarData(
        spots:    [FlSpot(avgGold, avgDamage), FlSpot(maxX, avgDamage)],
        color:    Colors.transparent, barWidth: 0,
        dotData:  const FlDotData(show: false),
        aboveBarData: BarAreaData(show: true, color: kStatGold.withValues(alpha: 0.07)),
      ),
      // Abajo-izquierda: poco oro, poco daño → bajo impacto (gris)
      LineChartBarData(
        spots:    [FlSpot(minX, avgDamage), FlSpot(avgGold, avgDamage)],
        color:    Colors.transparent, barWidth: 0,
        dotData:  const FlDotData(show: false),
        belowBarData: BarAreaData(show: true, color: kStatGray.withValues(alpha: 0.07)),
      ),
      // Abajo-derecha: mucho oro, poco daño → ineficiente (rojo)
      LineChartBarData(
        spots:    [FlSpot(avgGold, avgDamage), FlSpot(maxX, avgDamage)],
        color:    Colors.transparent, barWidth: 0,
        dotData:  const FlDotData(show: false),
        belowBarData: BarAreaData(show: true, color: kStatRed.withValues(alpha: 0.07)),
      ),

      // ── Diagonal Y=X ──────────────────────────────────────────────────────
      if (hasDiag)
        LineChartBarData(
          spots:            [FlSpot(diagStart, diagStart), FlSpot(diagEnd, diagEnd)],
          color:            kMuted.withValues(alpha: 0.28),
          barWidth:         1.5,
          dashArray:        [6, 5],
          isStrokeCapRound: true,
          dotData:          const FlDotData(show: false),
        ),

      // ── Vectores radiales centro → partida ────────────────────────────────
      for (final m in matches)
        LineChartBarData(
          spots: [FlSpot(avgGold, avgDamage), FlSpot(m.goldShare, m.damageShare)],
          color: kMuted.withValues(alpha: hasHover ? 0.06 : 0.16),
          barWidth: 1,
          dotData: const FlDotData(show: false),
        ),

      // ── Puntos individuales ───────────────────────────────────────────────
      LineChartBarData(
        spots: [
          for (int i = 0; i < matches.length; i++)
            FlSpot(matches[i].goldShare, matches[i].damageShare),
        ],
        color:    Colors.transparent,
        barWidth: 0,
        isCurved: false,
        dotData: FlDotData(
          show: true,
          getDotPainter: (spot, pct, bar, index) {
            final isHovered  = _hoveredIndex == index;
            final c          = matches[index].win ? kStatGreen : kStatRed;
            final double r   = hasHover
                ? (isHovered ? baseRadius * 1.4 : baseRadius * 0.65)
                : baseRadius;
            final double sw  = hasHover
                ? (isHovered ? baseStroke * 1.2 : baseStroke * 0.5)
                : baseStroke;
            final double a   = hasHover ? (isHovered ? 1.0 : 0.25) : 1.0;
            return FlDotCirclePainter(
              radius:      r,
              color:       c.withValues(alpha: a),
              strokeColor: kBgColor.withValues(alpha: a),
              strokeWidth: sw,
            );
          },
        ),
      ),

      // ── Centro de masa ────────────────────────────────────────────────────
      LineChartBarData(
        spots:    [FlSpot(avgGold, avgDamage)],
        color:    Colors.transparent,
        barWidth: 0,
        dotData: FlDotData(
          show: true,
          getDotPainter: (spot, pct, bar, index) => _GlowDotPainter(
            radius:    7,
            coreColor: const Color(0xFFFFFDE8),
            glowColor: const Color(0xFFFFE566),
            // se atenúa solo cuando hay un dot de partida en hover, no cuando se hace hover sobre sí mismo
            dimmed:    hasHover,
          ),
        ),
      ),
    ];

    return Column(
      children: [

        // ── Badge fijo del centro de masa ─────────────────────────────────────
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: const Color(0xFFFFE566).withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFFFFE566).withValues(alpha: 0.40)),
          ),
          child: Text(
            'CENTER OF MASS  ·  Gold ${avgGold.toStringAsFixed(1)}%  ·  Dmg ${avgDamage.toStringAsFixed(1)}%',
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Color(0xFFFFE566),
              fontSize: 11,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.4,
            ),
          ),
        ),
        const SizedBox(height: 10),

        SizedBox(
          height: 280,
          child: LineChart(
            LineChartData(
              minX: minX, maxX: maxX,
              minY: minY, maxY: maxY,
              lineBarsData: lineBarsData,

              extraLinesData: ExtraLinesData(
                extraLinesOnTop: false,
                horizontalLines: [
                  // Línea de cuadrante (centro de masa)
                  HorizontalLine(
                    y:           avgDamage,
                    color:       kMuted.withValues(alpha: hasHover ? 0.06 : 0.18),
                    strokeWidth: 1,
                    dashArray:   [4, 4],
                  ),
                  // Crosshair horizontal del dot en hover
                  if (_hoveredIndex != null && _hoveredIndex! >= 0)
                    HorizontalLine(
                      y:           matches[_hoveredIndex!].damageShare,
                      color:       (matches[_hoveredIndex!].win ? kStatGreen : kStatRed)
                                       .withValues(alpha: 0.35),
                      strokeWidth: 1,
                      dashArray:   [3, 3],
                    ),
                ],
                verticalLines: [
                  // Línea de cuadrante (centro de masa)
                  VerticalLine(
                    x:           avgGold,
                    color:       kMuted.withValues(alpha: hasHover ? 0.06 : 0.18),
                    strokeWidth: 1,
                    dashArray:   [4, 4],
                  ),
                  // Crosshair vertical del dot en hover
                  if (_hoveredIndex != null && _hoveredIndex! >= 0)
                    VerticalLine(
                      x:           matches[_hoveredIndex!].goldShare,
                      color:       (matches[_hoveredIndex!].win ? kStatGreen : kStatRed)
                                       .withValues(alpha: 0.35),
                      strokeWidth: 1,
                      dashArray:   [3, 3],
                    ),
                ],
              ),

              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                getDrawingHorizontalLine: (_) =>
                    FlLine(color: kBorderColor.withValues(alpha: 0.15), strokeWidth: 1),
              ),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  axisNameWidget: const Padding(
                    padding: EdgeInsets.only(bottom: 6),
                    child: Text('Damage Share %', style: TextStyle(fontSize: 9, color: kMuted)),
                  ),
                  axisNameSize: 18,
                  sideTitles: SideTitles(
                    showTitles:   true,
                    reservedSize: 40,
                    interval:     5,
                    getTitlesWidget: (v, meta) {
                      if (v == meta.min || v == meta.max) return const SizedBox.shrink();
                      return Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: Text('${v.toInt()}%', style: const TextStyle(fontSize: 9, color: kMuted)),
                      );
                    },
                  ),
                ),
                bottomTitles: AxisTitles(
                  axisNameWidget: const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text('Gold Share %', style: TextStyle(fontSize: 9, color: kMuted)),
                  ),
                  axisNameSize: 18,
                  sideTitles: SideTitles(
                    showTitles:   true,
                    reservedSize: 28,
                    interval:     5,
                    getTitlesWidget: (v, meta) {
                      if (v == meta.min || v == meta.max) return const SizedBox.shrink();
                      return Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text('${v.toInt()}%', style: const TextStyle(fontSize: 9, color: kMuted)),
                      );
                    },
                  ),
                ),
                rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                topTitles:   const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              ),

              lineTouchData: LineTouchData(
                touchSpotThreshold: 8,
                getTouchedSpotIndicator: (barData, spotIndexes) =>
                    spotIndexes.map((_) => null).toList(),
                touchCallback: (event, response) {
                  if (!event.isInterestedForInteractions ||
                      response == null ||
                      response.lineBarSpots == null ||
                      response.lineBarSpots!.isEmpty) {
                    setState(() => _hoveredIndex = null);
                    return;
                  }
                  // Priorizar el bar de partidas sobre vectores/diagonal
                  // (los endpoints de los vectores coinciden con los dots)
                  final matchSpot = response.lineBarSpots!
                      .where((s) => s.barIndex == matchBarIdx)
                      .firstOrNull;
                  final centerSpot = response.lineBarSpots!
                      .where((s) => s.barIndex == centerBarIdx)
                      .firstOrNull;
                  if (matchSpot != null) {
                    setState(() => _hoveredIndex = matchSpot.spotIndex);
                  } else if (centerSpot != null) {
                    setState(() => _hoveredIndex = null); // centro: sin hover de partida
                  } else {
                    setState(() => _hoveredIndex = null);
                  }
                },
                touchTooltipData: LineTouchTooltipData(
                  getTooltipColor: (_) => kSurface2,
                  getTooltipItems: (spots) {
                    return spots.map((spot) {
                      if (spot.barIndex == matchBarIdx) {
                        final m = matches[spot.spotIndex];
                        return LineTooltipItem(
                          '${m.champion}\n',
                          const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: kForeground),
                          textAlign: TextAlign.center,
                          children: [
                            TextSpan(
                              text:  m.win ? 'WIN' : 'LOSS',
                              style: TextStyle(
                                fontSize: 10, fontWeight: FontWeight.bold,
                                color: m.win ? kStatGreen : kStatRed,
                              ),
                            ),
                            TextSpan(
                              text: '\nGold  ${m.goldShare.toStringAsFixed(1)}%'
                                    '\nDmg   ${m.damageShare.toStringAsFixed(1)}%',
                              style: const TextStyle(fontSize: 9, color: kMuted),
                            ),
                          ],
                        );
                      }
                      return null; // centro de masa y vectores: sin tooltip
                    }).toList();
                  },
                ),
              ),
            ),
          ),
        ),

        const SizedBox(height: 10),

        Wrap(
          alignment:  WrapAlignment.center,
          spacing:    14,
          runSpacing: 4,
          children: const [
            LegendDot(color: Color(0xFFFFF9CC), label: 'Center of mass'),
            LegendDot(color: kStatGreen, label: 'Win'),
            LegendDot(color: kStatRed,   label: 'Loss'),
            LegendLine(color: kMuted, label: 'Equilibrium (Y=X)', dashed: true),
          ],
        ),

        const SizedBox(height: 16),

        Wrap(
          alignment: WrapAlignment.center,
          spacing: 16,
          runSpacing: 10,
          children: [
            MiniStat(label: 'AVG GOLD SHARE', value: '${avgGold.toStringAsFixed(1)}%'),
            MiniStat(label: 'AVG DMG SHARE',  value: '${avgDamage.toStringAsFixed(1)}%'),
            MiniStat(label: 'EFFICIENCY',     value: eff.toStringAsFixed(2),  color: effColor),
            MiniStat(label: 'CONSISTENCY',    value: consistencyLabel,         color: consistencyColor),
          ],
        ),
      ],
    );
  }
}

// ── Quadrant legend item (pequeño cuadrado de color) ─────────────────────────

class _QuadLegendItem extends StatelessWidget {
  const _QuadLegendItem({required this.color, required this.label});
  final Color  color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color:        color.withValues(alpha: 0.30),
            borderRadius: BorderRadius.circular(2),
            border:       Border.all(color: color.withValues(alpha: 0.70), width: 1),
          ),
        ),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(fontSize: 9, color: kMuted)),
      ],
    );
  }
}
