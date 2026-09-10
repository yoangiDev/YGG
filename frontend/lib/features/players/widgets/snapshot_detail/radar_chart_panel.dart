import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/snapshot_dashboard_model.dart' hide RadarChartData;
import 'avg_stats_logic.dart';
import 'chart_shared_widgets.dart';

const _kRankColors = <String, Color>{
  'CHALLENGER':  Color(0xFFF0D020),
  'GRANDMASTER': Color(0xFFE04030),
  'MASTER':      Color(0xFFA050D0),
  'DIAMOND':     Color(0xFF5090F0),
  'EMERALD':     Color(0xFF2ECC6E),
};

class RadarChartPanel extends StatelessWidget {
  const RadarChartPanel({
    super.key,
    required this.dashboardAsync,
    this.champion,
  });

  final AsyncValue<SnapshotDashboardModel> dashboardAsync;
  final String? champion;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return ChartCard(
      title: 'Performance Radar',
      subtitle: '0 = worst · Challenger avg ≈ 82 · Deaths: lower is better',
      onFullscreen: narrow && !chartIsInFullscreen(context)
          ? () => FullscreenChartScreen.push(
                context,
                RadarChartPanel(dashboardAsync: dashboardAsync, champion: champion),
              )
          : null,
      child: dashboardAsync.when(
        loading: () => const SizedBox(
          height: 300,
          child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: kPrimary)),
        ),
        error: (e, _) => const SizedBox(
          height: 300,
          child: Center(child: Text('Error loading data', style: TextStyle(color: kMuted, fontSize: 12))),
        ),
        data: _buildContent,
      ),
    );
  }

  Widget _buildContent(SnapshotDashboardModel dashboard) {
    final radarData     = dashboard.radarData;
    final axes          = radarData.axes;
    final playerDs      = radarData.playerDataset;
    final rankDatasets  = radarData.rankDatasets;

    if (axes.isEmpty) {
      return const SizedBox(
        height: 140,
        child: Center(child: Text('Not enough data', style: TextStyle(color: kMuted, fontSize: 12))),
      );
    }

    final playerNorm = axes.map((a) => (playerDs.normalizedValues[a] ?? 0.0).clamp(0.0, 100.0)).toList();
    final playerReal = axes.map((a) => playerDs.values[a] ?? 0.0).toList();

    final dataSets = <RadarDataSet>[
      RadarDataSet(
        fillColor:   kPrimary.withValues(alpha: 0.18),
        borderColor: kPrimary,
        borderWidth: 2,
        entryRadius: 3,
        dataEntries: playerNorm.map((v) => RadarEntry(value: v)).toList(),
      ),
      for (final entry in rankDatasets.entries)
        RadarDataSet(
          fillColor:   Colors.transparent,
          borderColor: (_kRankColors[entry.key] ?? kMuted).withValues(alpha: 0.55),
          borderWidth: 1.5,
          entryRadius: 0,
          dataEntries: axes
              .map((a) => RadarEntry(value: (entry.value.normalizedValues[a] ?? 0.0).clamp(0.0, 100.0)))
              .toList(),
        ),
    ];

    return Column(
      children: [
        if (champion != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Text(
              'Radar shows full snapshot data (champion filter not applied)',
              style: TextStyle(fontSize: 10, color: kMuted.withValues(alpha: 0.7), fontStyle: FontStyle.italic),
              textAlign: TextAlign.center,
            ),
          ),

        SizedBox(
          height: 300,
          child: RadarChart(
            RadarChartData(
              dataSets:                     dataSets,
              radarBackgroundColor:         Colors.transparent,
              borderData:                   FlBorderData(show: false),
              radarBorderData:              BorderSide(color: kBorderColor.withValues(alpha: 0.3), width: 1),
              tickBorderData:               BorderSide(color: kBorderColor.withValues(alpha: 0.15), width: 1),
              gridBorderData:               BorderSide(color: kBorderColor.withValues(alpha: 0.25), width: 1),
              ticksTextStyle:               const TextStyle(color: Colors.transparent, fontSize: 0),
              titleTextStyle:               const TextStyle(color: kMuted, fontSize: 10, fontWeight: FontWeight.w500),
              titlePositionPercentageOffset: 0.12,
              tickCount:                    4,
              getTitle: (index, _) => RadarChartTitle(text: axes[index]),
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Actual values badges
        Wrap(
          alignment:  WrapAlignment.center,
          spacing:    8,
          runSpacing: 8,
          children: [
            for (int i = 0; i < axes.length; i++)
              _MetricBadge(
                label: axes[i],
                value: playerReal[i],
                score: playerNorm[i],
                role: dashboard.activeRole,
              ),
          ],
        ),

        if (rankDatasets.isNotEmpty) ...[
          const SizedBox(height: 14),
          Wrap(
            alignment:  WrapAlignment.center,
            spacing:    12,
            runSpacing: 4,
            children: [
              LegendLine(color: kPrimary, label: playerDs.label),
              for (final entry in rankDatasets.entries)
                LegendLine(
                  color:  _kRankColors[entry.key] ?? kMuted,
                  label:  entry.key,
                  dashed: true,
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _MetricBadge extends StatelessWidget {
  const _MetricBadge({
    required this.label,
    required this.value,
    required this.score,
    required this.role,
  });

  final String label;
  final double value;
  final double score;
  final String role;

  Color get _color => getStatColor(label, checkStatus(label, value, role));

  String get _formatted {
    if (value >= 10000) return value.toStringAsFixed(0);
    if (value >= 100)   return value.toStringAsFixed(0);
    if (value % 1 == 0) return value.toStringAsFixed(0);
    return value.toStringAsFixed(1);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 96,
      height: 78,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color:        kSurface2,
        borderRadius: BorderRadius.circular(6),
        border:       Border.all(color: _color.withValues(alpha: 0.35)),
      ),
      child: Column(
        mainAxisSize:      MainAxisSize.max,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            height: 26,
            child: Center(
              child: Text(
                label,
                style: const TextStyle(fontSize: 9, color: kMuted, letterSpacing: 0.4),
                textAlign: TextAlign.center,
                maxLines: 2,
              ),
            ),
          ),
          const SizedBox(height: 3),
          Text(_formatted, style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: _color)),
          Text(
            '${score.toStringAsFixed(0)}/100',
            style: TextStyle(fontSize: 9, color: _color.withValues(alpha: 0.65)),
          ),
        ],
      ),
    );
  }
}
