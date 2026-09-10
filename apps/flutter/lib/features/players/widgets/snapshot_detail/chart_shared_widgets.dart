import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/theme/app_theme.dart';

// ── Fullscreen scope ──────────────────────────────────────────────────────────
// Marca el subárbol como "ya estamos en fullscreen" para que los botones
// no aparezcan de nuevo dentro de la pantalla de fullscreen.

class _ChartFullscreenScope extends InheritedWidget {
  const _ChartFullscreenScope({required super.child});

  static bool of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<_ChartFullscreenScope>() != null;

  @override
  bool updateShouldNotify(_ChartFullscreenScope old) => false;
}

/// Llama a esto desde un chart widget para saber si ya está en fullscreen.
bool chartIsInFullscreen(BuildContext context) => _ChartFullscreenScope.of(context);

// ── ChartCard ─────────────────────────────────────────────────────────────────

class ChartCard extends StatelessWidget {
  const ChartCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.child,
    this.headerTrailing,
    this.onFullscreen,
  });
  final String         title;
  final String         subtitle;
  final Widget         child;
  final Widget?        headerTrailing;
  final VoidCallback?  onFullscreen;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;

    final titleBlock = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: kForeground)),
        const SizedBox(height: 3),
        Text(subtitle, style: const TextStyle(fontSize: 10, color: kMuted)),
      ],
    );

    Widget headerWidget;

    if (!narrow) {
      // ── Desktop: layout original, sin botón fullscreen ────────────────────
      headerWidget = Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: titleBlock),
          if (headerTrailing != null) ...[
            const SizedBox(width: 12),
            headerTrailing!,
          ],
        ],
      );
    } else {
      // ── Móvil: título + botón fullscreen (si aplica) ──────────────────────
      final titleRow = onFullscreen != null
          ? Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: titleBlock),
                const SizedBox(width: 8),
                _FullscreenBtn(onTap: onFullscreen!),
              ],
            )
          : titleBlock;

      headerWidget = headerTrailing != null
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                titleRow,
                const SizedBox(height: 10),
                headerTrailing!,
              ],
            )
          : titleRow;
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kBorderColor.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          headerWidget,
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }
}

// ── Botón fullscreen (móvil) ──────────────────────────────────────────────────

class _FullscreenBtn extends StatelessWidget {
  const _FullscreenBtn({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(5),
        decoration: BoxDecoration(
          color: kPrimary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: kPrimary.withValues(alpha: 0.3)),
        ),
        child: const Icon(Icons.fullscreen, size: 16, color: kPrimaryLight),
      ),
    );
  }
}

// ── Pantalla fullscreen (solo móvil) ─────────────────────────────────────────

class FullscreenChartScreen extends StatefulWidget {
  const FullscreenChartScreen({super.key, required this.child});
  final Widget child;

  static void push(BuildContext context, Widget child) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => FullscreenChartScreen(child: child),
    ));
  }

  @override
  State<FullscreenChartScreen> createState() => _FullscreenChartScreenState();
}

class _FullscreenChartScreenState extends State<FullscreenChartScreen> {
  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
  }

  @override
  void dispose() {
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBgColor,
      body: SafeArea(
        child: _ChartFullscreenScope(
          child: Column(
            children: [
              // ── Barra superior ───────────────────────────────────────────
              Container(
                padding: const EdgeInsets.fromLTRB(16, 8, 12, 8),
                decoration: BoxDecoration(
                  color: kSurfaceColor,
                  border: Border(
                    bottom: BorderSide(color: kBorderColor.withValues(alpha: 0.4)),
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 3, height: 14,
                      decoration: BoxDecoration(
                        color: kPrimary.withValues(alpha: 0.8),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text(
                      'FULLSCREEN',
                      style: TextStyle(
                        fontSize: 9,
                        color: kMuted,
                        letterSpacing: 1.8,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    GestureDetector(
                      onTap: () => Navigator.of(context).pop(),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: kSurface2,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: kBorderColor.withValues(alpha: 0.5)),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.fullscreen_exit, size: 14, color: kMuted),
                            SizedBox(width: 5),
                            Text(
                              'EXIT',
                              style: TextStyle(
                                fontSize: 9,
                                color: kMuted,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.2,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // ── Contenido de la gráfica ──────────────────────────────────
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(12),
                  child: widget.child,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Resto de widgets compartidos (sin cambios) ────────────────────────────────

class MetricChip extends StatelessWidget {
  const MetricChip({super.key, required this.label, required this.selected, required this.onTap});
  final String       label;
  final bool         selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
        decoration: BoxDecoration(
          color:        selected ? kPrimary.withValues(alpha: 0.2) : kSurface2,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(
            color: selected ? kPrimary : kBorderColor.withValues(alpha: 0.5),
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Text(label,
            style: TextStyle(
              fontSize:   11,
              fontWeight: FontWeight.w600,
              color:      selected ? kPrimaryLight : kMuted,
            )),
      ),
    );
  }
}

class LegendDot extends StatelessWidget {
  const LegendDot({super.key, required this.color, required this.label});
  final Color  color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(shape: BoxShape.circle, color: color)),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(fontSize: 9, color: kMuted)),
      ],
    );
  }
}

class LegendLine extends StatelessWidget {
  const LegendLine({super.key, required this.color, required this.label, this.dashed = false});
  final Color  color;
  final String label;
  final bool   dashed;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        CustomPaint(size: const Size(20, 10), painter: LineLegendPainter(color: color, dashed: dashed)),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(fontSize: 9, color: kMuted)),
      ],
    );
  }
}

class LineLegendPainter extends CustomPainter {
  const LineLegendPainter({required this.color, required this.dashed});
  final Color color;
  final bool  dashed;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color..strokeWidth = 2..style = PaintingStyle.stroke;
    final cy = size.height / 2;
    if (dashed) {
      double x = 0;
      while (x < size.width) {
        canvas.drawLine(Offset(x, cy), Offset(math.min(x + 4, size.width), cy), paint);
        x += 7;
      }
    } else {
      canvas.drawLine(Offset(0, cy), Offset(size.width, cy), paint);
    }
  }

  @override
  bool shouldRepaint(LineLegendPainter old) => false;
}

class MiniStat extends StatelessWidget {
  const MiniStat({super.key, required this.label, required this.value, this.color});
  final String label;
  final String value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 8, color: kMuted, letterSpacing: 1.2, fontWeight: FontWeight.w600)),
        const SizedBox(height: 3),
        Text(value, style: TextStyle(fontSize: 17, color: color ?? kForeground, fontWeight: FontWeight.bold)),
      ],
    );
  }
}

class ChartPlaceholder extends StatelessWidget {
  const ChartPlaceholder({super.key, required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 200,
      width: double.infinity,
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kBorderColor.withValues(alpha: 0.4)),
      ),
      child: Center(
        child: Text(label, style: const TextStyle(color: kMuted, fontSize: 12)),
      ),
    );
  }
}

enum TrendDirection { improving, declining, stable }

TrendDirection trendDirectionFromRegression({
  required List<FlSpot> regrSpots,
  required int pointCount,
  required double avg,
}) {
  if (regrSpots.length != 2 || pointCount < 2) return TrendDirection.stable;
  final slope = (regrSpots[1].y - regrSpots[0].y) / (regrSpots[1].x - regrSpots[0].x);
  final totalChange = slope * (pointCount - 1);
  final threshold = avg.abs() * 0.10;
  if (totalChange > threshold) return TrendDirection.improving;
  if (totalChange < -threshold) return TrendDirection.declining;
  return TrendDirection.stable;
}

class TrendIndicator extends StatelessWidget {
  const TrendIndicator({super.key, required this.direction});
  final TrendDirection direction;

  @override
  Widget build(BuildContext context) {
    final (IconData icon, String label, Color color) = switch (direction) {
      TrendDirection.improving => (Icons.trending_up, 'Improving', kStatGreen),
      TrendDirection.declining => (Icons.trending_down, 'Declining', kStatRed),
      TrendDirection.stable    => (Icons.trending_flat, 'Stable', kStatGray),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color:        color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border:       Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }
}
