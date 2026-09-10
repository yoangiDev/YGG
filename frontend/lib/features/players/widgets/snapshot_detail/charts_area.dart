import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/shimmer.dart';
import '../../providers/snapshot_provider.dart';
import 'damage_gold_chart.dart';
import 'dragon_objective_panel.dart';
import 'heatmaps/map_heatmaps_panel.dart';
import 'lane_control_chart.dart';
import 'moving_average_chart.dart';
import 'radar_chart_panel.dart';

class ChartsArea extends ConsumerStatefulWidget {
  const ChartsArea({super.key, required this.snapshotId, this.champion});
  final int     snapshotId;
  final String? champion;

  @override
  ConsumerState<ChartsArea> createState() => _ChartsAreaState();
}

class _ChartsAreaState extends ConsumerState<ChartsArea> {
  Timer? _secondaryChartsTimer;
  bool _showSecondaryCharts = false;

  @override
  void initState() {
    super.initState();
    _scheduleSecondaryCharts();
  }

  @override
  void didUpdateWidget(covariant ChartsArea oldWidget) {
    super.didUpdateWidget(oldWidget);
    final changedSnapshot = oldWidget.snapshotId != widget.snapshotId;
    final changedChampion = oldWidget.champion != widget.champion;
    if (changedSnapshot || changedChampion) {
      _showSecondaryCharts = false;
      _scheduleSecondaryCharts();
    }
  }

  void _scheduleSecondaryCharts() {
    _secondaryChartsTimer?.cancel();
    _secondaryChartsTimer = Timer(const Duration(milliseconds: 220), () {
      if (mounted) {
        setState(() => _showSecondaryCharts = true);
      }
    });
  }

  @override
  void dispose() {
    _secondaryChartsTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dashboardAsync = ref.watch(snapshotDashboardProvider(widget.snapshotId));
    final activeRole = dashboardAsync.valueOrNull?.activeRole ?? 'MID';
    final loadingSecondaryPlaceholder = _LoadingChartPlaceholder(
      showJungleBlock: activeRole == 'JUNGLE',
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        RepaintBoundary(
          child: MovingAverageChart(dashboardAsync: dashboardAsync, champion: widget.champion),
        ),
        const SizedBox(height: 20),
        RepaintBoundary(
          child: LaneControlChart(snapshotId: widget.snapshotId, champion: widget.champion),
        ),
        const SizedBox(height: 20),
        RepaintBoundary(
          child: DamageGoldChart(snapshotId: widget.snapshotId, champion: widget.champion),
        ),
        const SizedBox(height: 20),
        if (!_showSecondaryCharts)
          loadingSecondaryPlaceholder
        else ...[
          RepaintBoundary(
            child: RadarChartPanel(dashboardAsync: dashboardAsync, champion: widget.champion),
          ),
          const SizedBox(height: 20),
          if (activeRole == 'JUNGLE') ...[
            RepaintBoundary(
              child: DragonObjectivePanel(snapshotId: widget.snapshotId, champion: widget.champion),
            ),
            const SizedBox(height: 20),
          ],
          RepaintBoundary(
            child: MapHeatmapsPanel(
              snapshotId: widget.snapshotId,
              activeRole: activeRole,
              champion: widget.champion,
            ),
          ),
        ],
      ],
    );
  }
}

class _LoadingChartPlaceholder extends StatelessWidget {
  const _LoadingChartPlaceholder({required this.showJungleBlock});

  final bool showJungleBlock;

  @override
  Widget build(BuildContext context) {
    return Shimmer(
      child: Column(
        children: [
          // Radar chart
          _ShimmerChartCard(contentHeight: 260),
          const SizedBox(height: 20),
          // Dragon objectives (solo jungle)
          if (showJungleBlock) ...[
            _ShimmerChartCard(contentHeight: 160),
            const SizedBox(height: 20),
          ],
          // Map heatmap
          _ShimmerChartCard(contentHeight: 200),
        ],
      ),
    );
  }
}

class _ShimmerChartCard extends StatelessWidget {
  const _ShimmerChartCard({required this.contentHeight});
  final double contentHeight;

  @override
  Widget build(BuildContext context) {
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
          // Header: imita ChartCard (título + botón fullscreen en móvil)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const ShimmerBox(width: 160, height: 14),
                    const SizedBox(height: 4),
                    const ShimmerBox(width: 220, height: 10),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              // Placeholder del botón fullscreen (solo reserva espacio)
              const ShimmerBox(width: 26, height: 26, radius: 6),
            ],
          ),
          const SizedBox(height: 18),
          // Contenido del gráfico
          ShimmerBox(height: contentHeight, radius: 8),
        ],
      ),
    );
  }
}