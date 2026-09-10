import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/match_model.dart';
import '../../providers/match_provider.dart';
import 'chart_math.dart';
import 'chart_shared_widgets.dart';

enum LaneMetric { goldDiff8, goldDiff14, goldDiff25, csDiff8, csDiff14, csDiff25, xpDiff8, xpDiff14, questTimeDiff }

class LaneControlChart extends ConsumerStatefulWidget {
  const LaneControlChart({super.key, required this.snapshotId, this.champion});
  final int     snapshotId;
  final String? champion;

  @override
  ConsumerState<LaneControlChart> createState() => _LaneControlChartState();
}

class _LaneControlChartState extends ConsumerState<LaneControlChart> {
  LaneMetric _metric = LaneMetric.goldDiff14;
  bool _showProgressionVectors = false;
  int? _hoveredBarIndex;

  String _metricLabel() => switch (_metric) {
    LaneMetric.goldDiff8  => 'Gold @8',
    LaneMetric.goldDiff14 => 'Gold @14',
    LaneMetric.goldDiff25 => 'Gold @25',
    LaneMetric.csDiff8    => 'CS @8',
    LaneMetric.csDiff14   => 'CS @14',
    LaneMetric.csDiff25   => 'CS @25',
    LaneMetric.xpDiff8    => 'XP @8',
    LaneMetric.xpDiff14   => 'XP @14',
    LaneMetric.questTimeDiff => 'Quest vs Enemy',
  };

  int? _getValue(MatchModel m) => switch (_metric) {
    LaneMetric.goldDiff8  => m.goldDiff8,
    LaneMetric.goldDiff14 => m.goldDiff14,
    LaneMetric.goldDiff25 => m.goldDiff25,
    LaneMetric.csDiff8    => m.csDiff8,
    LaneMetric.csDiff14   => m.csDiff14,
    LaneMetric.csDiff25   => m.csDiff25,
    LaneMetric.xpDiff8    => m.xpDiff8,
    LaneMetric.xpDiff14   => m.xpDiff14,
    LaneMetric.questTimeDiff => m.questCompletionTimeDiff,
  };

  String _formatVal(double v) {
    if (_metric == LaneMetric.questTimeDiff) {
      return MatchModel.formatQuestDiff(v.round());
    }
    final sign = v >= 0 ? '+' : '';
    final n    = v.toStringAsFixed(0);
    return switch (_metric) {
      LaneMetric.goldDiff8  || LaneMetric.goldDiff14 || LaneMetric.goldDiff25 => '$sign${n}g',
      LaneMetric.xpDiff8   || LaneMetric.xpDiff14                              => '$sign${n}xp',
      _                                                                            => '$sign$n',
    };
  }

  double _getMatchFluctuation(MatchModel m) {
    if (_metric == LaneMetric.questTimeDiff) return 0.0;
    final bool isGold = _metric == LaneMetric.goldDiff8 || _metric == LaneMetric.goldDiff14 || _metric == LaneMetric.goldDiff25;
    final bool isCs = _metric == LaneMetric.csDiff8 || _metric == LaneMetric.csDiff14 || _metric == LaneMetric.csDiff25;
    final bool isXp = _metric == LaneMetric.xpDiff8 || _metric == LaneMetric.xpDiff14;

    if (isGold) {
      final double first = (m.goldDiff8 ?? m.goldDiff14 ?? 0).toDouble();
      final double last = (m.goldDiff25 ?? m.goldDiff14 ?? m.goldDiff8 ?? 0).toDouble();
      return last - first;
    } else if (isCs) {
      final double first = (m.csDiff8 ?? m.csDiff14 ?? 0).toDouble();
      final double last = (m.csDiff25 ?? m.csDiff14 ?? m.csDiff8 ?? 0).toDouble();
      return last - first;
    } else if (isXp) {
      final double first = (m.xpDiff8 ?? m.xpDiff14 ?? 0).toDouble();
      final double last = (m.xpDiff14 ?? m.xpDiff8 ?? 0).toDouble();
      return last - first;
    }
    return 0.0;
  }

  @override
  Widget build(BuildContext context) {
    final matchesAsync = ref.watch(snapshotMatchesProvider(widget.snapshotId));

    final narrow = MediaQuery.of(context).size.width < 600;
    return ChartCard(
      title:    'Lane Control Over Time',
      subtitle: 'Each dot is a game | Enable progression vectors to see advantage fluctuation',
      onFullscreen: narrow && !chartIsInFullscreen(context)
          ? () => FullscreenChartScreen.push(
                context,
                LaneControlChart(snapshotId: widget.snapshotId, champion: widget.champion),
              )
          : null,
      child: matchesAsync.when(
        loading: () => const SizedBox(height: 200, child: Center(child: CircularProgressIndicator(strokeWidth: 2))),
        error:   (e, _) => const SizedBox(height: 200, child: Center(child: Text('Error loading data', style: TextStyle(color: kMuted)))),
        data:    _buildContent,
      ),
    );
  }

  Widget _buildContent(List<MatchModel> allMatches) {
    var matches = allMatches;
    if (widget.champion != null) {
      matches = matches.where((m) => m.champion == widget.champion).toList();
    }

    matches = matches.where((m) => _getValue(m) != null).toList();
    matches.sort((a, b) => a.creationTime.compareTo(b.creationTime));

    if (matches.isEmpty) {
      return const Column(
        children: [
          SizedBox(height: 30),
          SizedBox(
            height: 120,
            child: Center(child: Text('Not enough data', style: TextStyle(color: kMuted, fontSize: 12))),
          ),
        ],
      );
    }

    final rawVals   = matches.map((m) => _getValue(m)!.toDouble()).toList();
    final rawSpots  = [for (int i = 0; i < rawVals.length; i++) FlSpot(i.toDouble(), rawVals[i])];
    final regrSpots = regressionLine(rawSpots);

    // Auto-scaling and Dynamic Zoom: include vector endpoints if toggled
    final List<double> allBoundsY = [...rawVals];
    if (_showProgressionVectors) {
      for (int i = 0; i < rawVals.length; i++) {
        allBoundsY.add(rawVals[i] + _getMatchFluctuation(matches[i]));
      }
    }
    final dataMin = allBoundsY.isNotEmpty ? allBoundsY.reduce(math.min) : 0.0;
    final dataMax = allBoundsY.isNotEmpty ? allBoundsY.reduce(math.max) : 0.0;
    final absMax  = math.max(dataMin.abs(), dataMax.abs());
    final pad     = absMax > 0 ? absMax * 0.15 : 50.0;
    final minY    = math.min(dataMin - pad, -pad);
    final maxY    = math.max(dataMax + pad,  pad);

    final avg   = rawVals.reduce((a, b) => a + b) / rawVals.length;
    final best  = rawVals.reduce(math.max);
    final worst = rawVals.reduce(math.min);

    // Toggle button: VECTORES DE PROGRESIÃ“N (Hextech-style pill button with glow)
    final progressionToggle = Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        GestureDetector(
          onTap: () => setState(() {
            _showProgressionVectors = !_showProgressionVectors;
            _hoveredBarIndex = null;
          }),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
            decoration: BoxDecoration(
              color: _showProgressionVectors ? kPrimary.withValues(alpha: 0.25) : kSurface2,
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: _showProgressionVectors ? kPrimaryLight : kBorderColor.withValues(alpha: 0.5),
                width: 1.5,
              ),
              boxShadow: [
                if (_showProgressionVectors)
                  BoxShadow(
                    color: kPrimary.withValues(alpha: 0.4),
                    blurRadius: 10,
                    spreadRadius: 1,
                  ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.trending_up,
                  size: 13,
                  color: _showProgressionVectors ? kPrimaryLight : kMuted,
                ),
                const SizedBox(width: 6),
                Text(
                  'PROGRESSION VECTORS',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.7,
                    color: _showProgressionVectors ? kForeground : kMuted,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );

    final List<LineChartBarData> lineBars = [];

    // Layer 0: Background zone (invisible line at y=0, fills green/red above/below)
    lineBars.add(
      LineChartBarData(
        spots:    [FlSpot(-0.5, 0), FlSpot((matches.length - 1).toDouble() + 0.5, 0)],
        barWidth: 0,
        color:    Colors.transparent,
        dotData:  const FlDotData(show: false),
        aboveBarData: BarAreaData(show: true, color: kStatGreen.withValues(alpha: 0.05)),
        belowBarData: BarAreaData(show: true, color: kStatRed.withValues(alpha: 0.05)),
      ),
    );

    // Layer 1: Progression Vectors (only if toggled active)
    if (_showProgressionVectors) {
      for (int i = 0; i < matches.length; i++) {
        final m = matches[i];
        final val = rawVals[i];
        final fluct = _getMatchFluctuation(m);

        final isHovered = _hoveredBarIndex == i;
        final hasActiveHover = _hoveredBarIndex != null;

        final double barWidth = hasActiveHover ? (isHovered ? 4.5 : 1.0) : 1.8;
        final double alpha = hasActiveHover ? (isHovered ? 0.95 : 0.18) : 0.45;
        final double dotRadius = hasActiveHover ? (isHovered ? 4.5 : 1.8) : 2.5;
        final double dotStroke = hasActiveHover ? (isHovered ? 1.5 : 0.6) : 0.8;

        final Color vectorColor = fluct > 0 ? kStatGreen : (fluct < 0 ? kStatRed : kStatGray);

        lineBars.add(
          LineChartBarData(
            spots: [
              FlSpot(i.toDouble(), val),
              FlSpot(i.toDouble() + 0.35, val + fluct),
            ],
            isCurved: false,
            color: vectorColor.withValues(alpha: alpha),
            barWidth: barWidth,
            dotData: FlDotData(
              show: true,
              getDotPainter: (spot, percent, bar, index) {
                if (index == 0) {
                  return FlDotCirclePainter(
                    radius: 0,
                    color: Colors.transparent,
                    strokeWidth: 0,
                    strokeColor: Colors.transparent,
                  );
                }
                return FlDotCirclePainter(
                  radius: dotRadius,
                  color: vectorColor.withValues(alpha: alpha),
                  strokeWidth: dotStroke,
                  strokeColor: kBgColor,
                );
              },
            ),
          ),
        );
      }
    }

    // Layer 2: Raw chronological spots (drawn on top of vector starting points)
    lineBars.add(
      LineChartBarData(
        spots:    rawSpots,
        barWidth: 0,
        dotData: FlDotData(
          show: true,
          getDotPainter: (spot, percent, bar, index) {
            final isHovered = _hoveredBarIndex == index;
            final hasActiveHover = _hoveredBarIndex != null;

            final r = hasActiveHover 
                ? (isHovered ? 6.0 : (rawVals.length > 80 ? 1.5 : rawVals.length > 40 ? 2.0 : 3.0))
                : (rawVals.length > 80 ? 2.0 : rawVals.length > 40 ? 3.0 : 4.5);
            final alpha = hasActiveHover 
                ? (isHovered ? 1.0 : 0.30)
                : 1.0;
            final double strokeWidth = hasActiveHover 
                ? (isHovered ? 1.8 : 0.6)
                : (rawVals.length > 40 ? 0.8 : 1.5);

            return FlDotCirclePainter(
              radius:      r,
              color:       (matches[index].win ? kStatGreen : kStatRed).withValues(alpha: alpha),
              strokeWidth: strokeWidth,
              strokeColor: kBgColor,
            );
          },
        ),
      ),
    );

    // Layer 3: Linear Regression Line (overall trend, faded if hovering a point/vector)
    if (regrSpots.length == 2) {
      lineBars.add(
        LineChartBarData(
          spots:     regrSpots,
          isCurved:  false,
          color:     kStatGold.withValues(alpha: _hoveredBarIndex != null ? 0.08 : 0.7),
          barWidth:  1.5,
          dotData:   const FlDotData(show: false),
          dashArray: [6, 4],
        ),
      );
    }

    return Column(
      children: [
        progressionToggle,
        const SizedBox(height: 12),
        // Selector de mÃ©trica original
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 6,
          runSpacing: 6,
          children: [
            MetricChip(label: 'Gold @8',  selected: _metric == LaneMetric.goldDiff8,  onTap: () => setState(() { _metric = LaneMetric.goldDiff8; _hoveredBarIndex = null; })),
            MetricChip(label: 'Gold @14', selected: _metric == LaneMetric.goldDiff14, onTap: () => setState(() { _metric = LaneMetric.goldDiff14; _hoveredBarIndex = null; })),
            MetricChip(label: 'Gold @25', selected: _metric == LaneMetric.goldDiff25, onTap: () => setState(() { _metric = LaneMetric.goldDiff25; _hoveredBarIndex = null; })),
            MetricChip(label: 'CS @8',    selected: _metric == LaneMetric.csDiff8,    onTap: () => setState(() { _metric = LaneMetric.csDiff8; _hoveredBarIndex = null; })),
            MetricChip(label: 'CS @14',   selected: _metric == LaneMetric.csDiff14,   onTap: () => setState(() { _metric = LaneMetric.csDiff14; _hoveredBarIndex = null; })),
            MetricChip(label: 'CS @25',   selected: _metric == LaneMetric.csDiff25,   onTap: () => setState(() { _metric = LaneMetric.csDiff25; _hoveredBarIndex = null; })),
            MetricChip(label: 'XP @8',    selected: _metric == LaneMetric.xpDiff8,    onTap: () => setState(() { _metric = LaneMetric.xpDiff8; _hoveredBarIndex = null; })),
            MetricChip(label: 'XP @14',   selected: _metric == LaneMetric.xpDiff14,   onTap: () => setState(() { _metric = LaneMetric.xpDiff14; _hoveredBarIndex = null; })),
            MetricChip(label: 'Quest vs Enemy', selected: _metric == LaneMetric.questTimeDiff, onTap: () => setState(() { _metric = LaneMetric.questTimeDiff; _hoveredBarIndex = null; })),
          ],
        ),
        const SizedBox(height: 10),

        if (regrSpots.length == 2 && _hoveredBarIndex == null)
          TrendIndicator(
            direction: trendDirectionFromRegression(
              regrSpots: regrSpots,
              pointCount: matches.length,
              avg: avg,
            ),
          ),
        if (_hoveredBarIndex != null) Builder(builder: (_) {
          // Si hay hover, mostrar el nombre del campeÃ³n enfocado arriba
          final m = matches[_hoveredBarIndex!];
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: (m.win ? kStatGreen : kStatRed).withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: (m.win ? kStatGreen : kStatRed).withValues(alpha: 0.35)),
            ),
            child: Text('${m.champion.toUpperCase()} (${m.win ? "WIN" : "LOSS"})',
              style: TextStyle(color: m.win ? kStatGreen : kStatRed, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 0.5)),
          );
        }),
        const SizedBox(height: 10),

        // GrÃ¡fica
        SizedBox(
          height: 240,
          child: LineChart(
            LineChartData(
              clipData: const FlClipData.all(),
              minX: -0.5,
              maxX: (matches.length - 1).toDouble() + 0.5,
              minY: minY,
              maxY: maxY,
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                getDrawingHorizontalLine: (_) =>
                    FlLine(color: kBorderColor.withValues(alpha: 0.15), strokeWidth: 1),
              ),
              extraLinesData: ExtraLinesData(
                horizontalLines: [
                  HorizontalLine(
                    y: 0,
                    color: kForeground.withValues(alpha: 0.25),
                    strokeWidth: 1,
                  ),
                ],
              ),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles:   true,
                    reservedSize: 44,
                    getTitlesWidget: (value, meta) {
                      if (value == meta.min || value == meta.max) return const SizedBox.shrink();
                      return Text(_formatVal(value),
                          style: const TextStyle(fontSize: 9, color: kMuted));
                    },
                  ),
                ),
                rightTitles:  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                topTitles:    const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles:   true,
                    interval:     1,
                    reservedSize: 20,
                    getTitlesWidget: (value, meta) {
                      if (value != value.truncateToDouble()) return const SizedBox.shrink();
                      final i = value.toInt();
                      if (i < 0 || i >= matches.length) return const SizedBox.shrink();
                      final step = math.max(1, matches.length ~/ 6);
                      if (i % step != 0) return const SizedBox.shrink();
                      final d = matches[i].creationTime;
                      return Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text('${d.day}/${d.month}',
                            style: const TextStyle(fontSize: 10, color: kMuted)),
                      );
                    },
                  ),
                ),
              ),
              borderData: FlBorderData(show: false),
              lineTouchData: LineTouchData(
                touchCallback: (FlTouchEvent event, lineTouchResponse) {
                  if (!event.isInterestedForInteractions ||
                      lineTouchResponse == null ||
                      lineTouchResponse.lineBarSpots == null ||
                      lineTouchResponse.lineBarSpots!.isEmpty) {
                    setState(() {
                      _hoveredBarIndex = null;
                    });
                    return;
                  }
                  final touchedSpot = lineTouchResponse.lineBarSpots!.first;
                  int? gameIndex;
                  if (_showProgressionVectors) {
                    final int N = matches.length;
                    if (touchedSpot.barIndex >= 1 && touchedSpot.barIndex <= N) {
                      gameIndex = touchedSpot.barIndex - 1;
                    } else if (touchedSpot.barIndex == N + 1) {
                      gameIndex = touchedSpot.spotIndex;
                    }
                  } else {
                    if (touchedSpot.barIndex == 1) {
                      gameIndex = touchedSpot.spotIndex;
                    }
                  }
                  setState(() {
                    _hoveredBarIndex = gameIndex;
                  });
                },
                touchTooltipData: LineTouchTooltipData(
                  getTooltipColor: (_) => kSurface2,
                  getTooltipItems: (spots) {
                    return spots.map((s) {
                      int? gameIndex;
                      if (_showProgressionVectors) {
                        final int N = matches.length;
                        if (s.barIndex >= 1 && s.barIndex <= N) {
                          gameIndex = s.barIndex - 1;
                        } else if (s.barIndex == N + 1) {
                          gameIndex = s.spotIndex;
                        }
                      } else {
                        if (s.barIndex == 1) {
                          gameIndex = s.spotIndex;
                        }
                      }

                      if (gameIndex == null) return null;
                      if (_hoveredBarIndex != null && gameIndex != _hoveredBarIndex) {
                        return null;
                      }
                      
                      final expectedBarIndex = _showProgressionVectors ? (matches.length + 1) : 1;
                      if (s.barIndex != expectedBarIndex) return null;

                      final m = matches[gameIndex];
                      final fluct = _getMatchFluctuation(m);
                      final sign = fluct >= 0 ? '+' : '';
                      final formattedFluct = _formatVal(fluct.abs());
                      
                      String trendText = '';
                      if (fluct > 0) {
                        trendText = '\nAdvantage: Growing ($sign$formattedFluct)';
                      } else if (fluct < 0) {
                        trendText = '\nAdvantage: Shrinking (-$formattedFluct)';
                      } else {
                        trendText = '\nAdvantage: Stable';
                      }

                      return LineTooltipItem(
                        '${m.champion} (${m.win ? 'WIN' : 'LOSS'})\n'
                        '${_metricLabel()}: ${_formatVal(s.y)}',
                        TextStyle(
                          color: m.win ? kStatGreen : kStatRed,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                        textAlign: TextAlign.center,
                        children: [
                          if (_showProgressionVectors)
                            TextSpan(
                              text: trendText,
                              style: TextStyle(
                                color: fluct > 0 ? kStatGreen : (fluct < 0 ? kStatRed : kMuted),
                                fontSize: 9,
                                fontWeight: FontWeight.normal,
                              ),
                            ),
                        ],
                      );
                    }).toList();
                  },
                ),
              ),
              lineBarsData: lineBars,
            ),
          ),
        ),
        const SizedBox(height: 10),

        // Leyenda
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 14,
          runSpacing: 4,
          children: [
            LegendDot(color: kStatGreen, label: 'Win'),
            LegendDot(color: kStatRed,   label: 'Loss'),
            LegendLine(color: kStatGold.withValues(alpha: 0.7), label: 'Trend', dashed: true),
            if (_showProgressionVectors) ...[
              LegendLine(color: kStatGreen.withValues(alpha: 0.8), label: 'Advantage UP'),
              LegendLine(color: kStatRed.withValues(alpha: 0.8), label: 'Advantage DOWN'),
            ],
          ],
        ),
        const SizedBox(height: 16),

        // Stats resumen
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 16,
          runSpacing: 10,
          children: [
            MiniStat(label: 'GAMES', value: '${matches.length}'),
            MiniStat(label: 'AVG',   value: _formatVal(avg)),
            MiniStat(label: 'BEST',  value: _formatVal(best)),
            MiniStat(label: 'WORST', value: _formatVal(worst)),
          ],
        ),
      ],
    );
  }
}