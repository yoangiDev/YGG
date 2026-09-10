import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/snapshot_dashboard_model.dart';
import 'chart_math.dart';
import 'chart_shared_widgets.dart';

enum TrendMetric { kda, csPerMin, goldPerMin, visionPerMin }

class MovingAverageChart extends StatefulWidget {
  const MovingAverageChart({super.key, required this.dashboardAsync, this.champion});
  final AsyncValue<SnapshotDashboardModel> dashboardAsync;
  final String? champion;

  @override
  State<MovingAverageChart> createState() => _MovingAverageChartState();
}

class _MovingAverageChartState extends State<MovingAverageChart> {
  TrendMetric _metric = TrendMetric.kda;
  bool _isMetricInitialized = false;
  bool _showChallengerLine = false;
  _TrendCacheEntry? _cache;

  // Medias de estadÃ­sticas de Challenger
  static const Map<String, Map<TrendMetric, double>> _kChallengerAverages = {
    'TOP': {
      TrendMetric.kda: 2.78,
      TrendMetric.csPerMin: 7.40,
      TrendMetric.goldPerMin: 430.87,
    },
    'JUNGLE': {
      TrendMetric.kda: 4.47,
      TrendMetric.csPerMin: 7.09,
      TrendMetric.visionPerMin: 1.04,
      TrendMetric.goldPerMin: 408.38,
    },
    'MID': {
      TrendMetric.kda: 3.54,
      TrendMetric.csPerMin: 7.51,
      TrendMetric.goldPerMin: 465.45,
    },
    'ADC': {
      TrendMetric.kda: 3.41,
      TrendMetric.csPerMin: 8.00,
      TrendMetric.goldPerMin: 518.74,
    },
    'SUPPORT': {
      TrendMetric.kda: 4.15,
      TrendMetric.visionPerMin: 2.87,
      TrendMetric.goldPerMin: 299.29,
    },
  };

  @override
  Widget build(BuildContext context) {
    String subtitle = 'Each dot is a game | Blue line = moving avg | Gold line = overall trend';
    if (widget.dashboardAsync.hasValue) {
      final dashboard = widget.dashboardAsync.value!;
      final trends = dashboard.performanceTrends;
      final wSize = (trends.length * 0.15).round().clamp(3, 10);
      subtitle = 'Each dot is a game | Blue line = last ${wSize}g avg | Gold line = overall trend';

      if (!_isMetricInitialized) {
        _isMetricInitialized = true;
        final activeRole = dashboard.activeRole.toUpperCase();
        if (activeRole == 'SUPPORT') {
          _metric = TrendMetric.visionPerMin;
        } else {
          _metric = TrendMetric.csPerMin;
        }
      }
    }

    final narrow = MediaQuery.of(context).size.width < 600;
    return ChartCard(
      title: 'Performance Over Time',
      subtitle: subtitle,
      onFullscreen: narrow && !chartIsInFullscreen(context)
          ? () => FullscreenChartScreen.push(
                context,
                MovingAverageChart(dashboardAsync: widget.dashboardAsync, champion: widget.champion),
              )
          : null,
      child: widget.dashboardAsync.when(
        loading: () => const SizedBox(height: 200, child: Center(child: CircularProgressIndicator(strokeWidth: 2))),
        error:   (e, _) => const SizedBox(height: 200, child: Center(child: Text('Error loading data', style: TextStyle(color: kMuted)))),
        data:    _buildContent,
      ),
    );
  }

  Widget _buildContent(SnapshotDashboardModel dashboard) {
    var trends = dashboard.performanceTrends;
    if (widget.champion != null) {
      trends = trends.where((t) => t.champion == widget.champion).toList();
    }

    if (trends.isEmpty) {
      return const SizedBox(
        height: 120,
        child: Center(child: Text('Not enough data', style: TextStyle(color: kMuted, fontSize: 12))),
      );
    }

    final wSize = (trends.length * 0.15).round().clamp(3, 10);

    final activeRole = dashboard.activeRole.toUpperCase();

    // Determinar quÃ© mÃ©tricas mostrar segÃºn el rol
    final List<TrendMetric> allowedMetrics;
    if (activeRole == 'SUPPORT') {
      allowedMetrics = [TrendMetric.kda, TrendMetric.visionPerMin, TrendMetric.goldPerMin];
    } else if (activeRole == 'JUNGLE') {
      allowedMetrics = [TrendMetric.kda, TrendMetric.csPerMin, TrendMetric.goldPerMin, TrendMetric.visionPerMin];
    } else {
      allowedMetrics = [TrendMetric.kda, TrendMetric.csPerMin, TrendMetric.goldPerMin];
    }

    // Asegurar que la mÃ©trica seleccionada es vÃ¡lida para este rol
    if (!allowedMetrics.contains(_metric)) {
      _metric = allowedMetrics.first;
    }

    final roleAvgs = _kChallengerAverages[activeRole] ?? _kChallengerAverages['MID']!;
    final challengerAvg = roleAvgs[_metric] ?? 0.0;
    final pointsKey = _buildCacheKey(trends: trends);
    if (_cache == null || _cache!.key != pointsKey) {
      final rawValues = trends.map(_getValue).toList(growable: false);
      final maValues = trends.map(_getMA).toList(growable: false);
      final rawSpots = [for (int i = 0; i < trends.length; i++) FlSpot(i.toDouble(), rawValues[i])];
      final maSpots = [for (int i = 0; i < trends.length; i++) FlSpot(i.toDouble(), maValues[i])];
      _cache = _TrendCacheEntry(
        key: pointsKey,
        rawValues: rawValues,
        maValues: maValues,
        rawSpots: rawSpots,
        maSpots: maSpots,
        regrSpots: regressionLine(rawSpots),
        minBase: [...rawValues, ...maValues].reduce(math.min),
        maxBase: [...rawValues, ...maValues].reduce(math.max),
      );
    }
    final cached = _cache!;
    final rawValues = cached.rawValues;
    final rawSpots = cached.rawSpots;
    final maSpots = cached.maSpots;
    final regrSpots = cached.regrSpots;

    final minY = _showChallengerLine ? math.min(cached.minBase, challengerAvg) : cached.minBase;
    final maxY = _showChallengerLine ? math.max(cached.maxBase, challengerAvg) : cached.maxBase;
    final range = maxY - minY;
    final pad = range > 0 ? range * 0.25 : 1.0;
    final interval = range > 0 ? range / 3 : 1.0;

    final avg = rawValues.reduce((a, b) => a + b) / rawValues.length;
    final best = rawValues.reduce(math.max);
    final worst = rawValues.reduce(math.min);
    final first = rawValues.first;
    final last = rawValues.last;

    return Column(
      children: [
        // Selector de métrica
        Builder(builder: (context) {
          final narrow = MediaQuery.of(context).size.width < 600;
          final challengerSize = narrow ? 40.0 : 54.0;
          final challengerButton = Tooltip(
            message: 'Toggle Challenger Comparison',
            child: GestureDetector(
              onTap: () => setState(() => _showChallengerLine = !_showChallengerLine),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.all(4),
                height: challengerSize,
                width: challengerSize,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _showChallengerLine ? kPrimary.withValues(alpha: 0.35) : kSurface2,
                  border: Border.all(
                    color: _showChallengerLine ? kPrimaryLight : kBorderColor.withValues(alpha: 0.5),
                    width: _showChallengerLine ? 2.0 : 1,
                  ),
                  boxShadow: [
                    if (_showChallengerLine)
                      BoxShadow(
                        color: kPrimary.withValues(alpha: 0.6),
                        blurRadius: 22,
                        spreadRadius: 4,
                      ),
                  ],
                ),
                child: AnimatedOpacity(
                  duration: const Duration(milliseconds: 200),
                  opacity: _showChallengerLine ? 1.0 : 0.45,
                  child: _showChallengerLine
                      ? Image.asset('assets/rank_badges/challenger_badge.png', fit: BoxFit.contain)
                      : ColorFiltered(
                          colorFilter: const ColorFilter.matrix(<double>[
                            0.2126, 0.7152, 0.0722, 0, 0,
                            0.2126, 0.7152, 0.0722, 0, 0,
                            0.2126, 0.7152, 0.0722, 0, 0,
                            0,      0,      0,      1, 0,
                          ]),
                          child: Image.asset('assets/rank_badges/challenger_badge.png', fit: BoxFit.contain),
                        ),
                ),
              ),
            ),
          );

          if (narrow) {
            return Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Expanded(
                  child: Wrap(
                    alignment: WrapAlignment.center,
                    spacing: 4,
                    runSpacing: 6,
                    children: allowedMetrics.map((m) => MetricChip(
                      label: _metricChipLabel(m),
                      selected: _metric == m,
                      onTap: () => setState(() => _metric = m),
                    )).toList(),
                  ),
                ),
                const SizedBox(width: 8),
                challengerButton,
              ],
            );
          }

          return Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              ...allowedMetrics.map((m) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: MetricChip(
                  label: _metricChipLabel(m),
                  selected: _metric == m,
                  onTap: () => setState(() => _metric = m),
                ),
              )),
              const SizedBox(width: 12),
              Container(height: 20, width: 1, color: kBorderColor.withValues(alpha: 0.6)),
              const SizedBox(width: 12),
              challengerButton,
            ],
          );
        }),
        const SizedBox(height: 10),

        if (regrSpots.length == 2)
          TrendIndicator(
            direction: trendDirectionFromRegression(
              regrSpots: regrSpots,
              pointCount: trends.length,
              avg: avg,
            ),
          ),
        const SizedBox(height: 10),

        // GrÃ¡fica
        SizedBox(
          height: 180,
          child: LineChart(
            LineChartData(
              clipData: const FlClipData.all(),
              minX: -0.5,
              maxX: (trends.length - 1).toDouble() + 0.5,
              minY: minY - pad,
              maxY: maxY + pad,
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                horizontalInterval: interval,
                getDrawingHorizontalLine: (_) =>
                    FlLine(color: kBorderColor.withValues(alpha: 0.25), strokeWidth: 1),
              ),
              titlesData: FlTitlesData(
                leftTitles:   const AxisTitles(sideTitles: SideTitles(showTitles: false)),
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
                      if (i < 0 || i >= trends.length) return const SizedBox.shrink();
                      if (!_labelIndices(trends).contains(i))  return const SizedBox.shrink();
                      final d = trends[i].creationTime;
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
              extraLinesData: ExtraLinesData(
                horizontalLines: [
                  if (_showChallengerLine)
                    HorizontalLine(
                      y: challengerAvg,
                      color: Colors.transparent,
                      strokeWidth: 0,
                      label: HorizontalLineLabel(
                        show: true,
                        alignment: Alignment.topRight,
                        padding: const EdgeInsets.only(right: 8, bottom: 2),
                        style: TextStyle(
                          color: kPrimaryLight.withValues(alpha: 0.85),
                          fontSize: 9,
                          fontWeight: FontWeight.bold,
                          backgroundColor: kBgColor.withValues(alpha: 0.45),
                        ),
                        labelResolver: (line) => 'CHALLENGER: ${challengerAvg.toStringAsFixed(1)}',
                      ),
                    ),
                ],
              ),
              lineTouchData: LineTouchData(
                touchTooltipData: LineTouchTooltipData(
                  getTooltipColor: (_) => kSurface2,
                  getTooltipItems: (spots) => spots.map((s) {
                    if (s.barIndex != 0) return null;
                    final t = trends[s.spotIndex];
                    return LineTooltipItem(
                      '${t.champion}\n${_metricLabel()}: ${s.y.toStringAsFixed(2)}\n',
                      const TextStyle(color: kForeground, fontSize: 10),
                      textAlign: TextAlign.center,
                      children: [
                        TextSpan(
                          text: t.win ? 'WIN' : 'LOSS',
                          style: TextStyle(
                            color:      t.win ? kStatGreen : kStatRed,
                            fontSize:   10,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    );
                  }).toList(),
                ),
              ),
              lineBarsData: [
                // Capa 1: puntos brutos
                LineChartBarData(
                  spots:    rawSpots,
                  barWidth: 0,
                  dotData: FlDotData(
                    show: true,
                    getDotPainter: (spot, percent, bar, index) {
                      final r = trends.length > 80 ? 2.0
                              : trends.length > 40 ? 3.0
                              : 4.5;
                      return FlDotCirclePainter(
                        radius:      r,
                        color:       trends[index].win ? kStatGreen : kStatRed,
                        strokeWidth: trends.length > 40 ? 0.8 : 1.5,
                        strokeColor: kBgColor,
                      );
                    },
                  ),
                ),
                // Capa 2: media mÃ³vil
                LineChartBarData(
                  spots:    maSpots,
                  isCurved: true,
                  color:    kStatBlue,
                  barWidth: 2.5,
                  dotData:  const FlDotData(show: false),
                  belowBarData: BarAreaData(show: true, color: kStatBlue.withValues(alpha: 0.07)),
                ),
                // Capa 3: regresiÃ³n lineal
                if (regrSpots.length == 2)
                  LineChartBarData(
                    spots:     regrSpots,
                    isCurved:  false,
                    color:     kStatGold.withValues(alpha: 0.7),
                    barWidth:  1.5,
                    dotData:   const FlDotData(show: false),
                    dashArray: [6, 4],
                  ),
                // Capa 4: lÃ­nea de Challenger (reemplaza la lÃ­nea horizontal unclipped de fl_chart)
                if (_showChallengerLine)
                  LineChartBarData(
                    spots: [
                      FlSpot(0.0, challengerAvg),
                      FlSpot((trends.length - 1).toDouble(), challengerAvg),
                    ],
                    isCurved:  false,
                    color:     kPrimary.withValues(alpha: 0.45),
                    barWidth:  1.0,
                    dotData:   const FlDotData(show: false),
                    dashArray: [5, 5],
                  ),
              ],
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
            LegendLine(color: kStatBlue, label: 'Moving avg (${wSize}g)'),
            LegendLine(color: kStatGold.withValues(alpha: 0.7), label: 'Trend', dashed: true),
            if (_showChallengerLine)
              LegendLine(color: kPrimary,  label: 'Challenger avg', dashed: true),
          ],
        ),
        const SizedBox(height: 16),

        // Stats resumen
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 16,
          runSpacing: 10,
          children: [
            MiniStat(label: 'AVG',        value: avg.toStringAsFixed(2)),
            MiniStat(label: 'MAX',        value: best.toStringAsFixed(2)),
            MiniStat(label: 'MIN',        value: worst.toStringAsFixed(2)),
            MiniStat(label: 'FIRST GAME', value: first.toStringAsFixed(2)),
            MiniStat(label: 'LAST GAME',  value: last.toStringAsFixed(2)),
          ],
        ),
      ],
    );
  }

  double _getValue(TrendPoint t) => switch (_metric) {
    TrendMetric.kda        => t.kda,
    TrendMetric.csPerMin   => t.csPerMin,
    TrendMetric.goldPerMin => t.goldPerMin,
    TrendMetric.visionPerMin => t.visionPerMin,
  };

  double _getMA(TrendPoint t) => switch (_metric) {
    TrendMetric.kda        => t.kdaMovingAvg,
    TrendMetric.csPerMin   => t.csMovingAvg,
    TrendMetric.goldPerMin => t.goldMovingAvg,
    TrendMetric.visionPerMin => t.visionMovingAvg,
  };

  String _metricLabel() => switch (_metric) {
    TrendMetric.kda        => 'KDA',
    TrendMetric.csPerMin   => 'CS/min',
    TrendMetric.goldPerMin => 'Gold/min',
    TrendMetric.visionPerMin => 'Vision/min',
  };

  String _metricChipLabel(TrendMetric m) => switch (m) {
    TrendMetric.kda        => 'KDA',
    TrendMetric.csPerMin   => 'CS / min',
    TrendMetric.goldPerMin => 'Gold / min',
    TrendMetric.visionPerMin => 'Vision / min',
  };

  Set<int> _labelIndices(List<TrendPoint> trends) {
    final step      = math.max(1, trends.length ~/ 6);
    final seenDates = <String>{};
    final result    = <int>{};
    for (int i = 0; i < trends.length; i += step) {
      final d   = trends[i].creationTime;
      final key = '${d.day}/${d.month}';
      if (seenDates.add(key)) result.add(i);
    }
    return result;
  }

  String _buildCacheKey({required List<TrendPoint> trends}) {
    final champKey = widget.champion ?? '_all_';
    final first = trends.first;
    final last = trends.last;
    return '${_metric.name}|$champKey|${trends.length}|${first.creationTime.millisecondsSinceEpoch}|${last.creationTime.millisecondsSinceEpoch}';
  }
}

class _TrendCacheEntry {
  const _TrendCacheEntry({
    required this.key,
    required this.rawValues,
    required this.maValues,
    required this.rawSpots,
    required this.maSpots,
    required this.regrSpots,
    required this.minBase,
    required this.maxBase,
  });

  final String key;
  final List<double> rawValues;
  final List<double> maValues;
  final List<FlSpot> rawSpots;
  final List<FlSpot> maSpots;
  final List<FlSpot> regrSpots;
  final double minBase;
  final double maxBase;
}