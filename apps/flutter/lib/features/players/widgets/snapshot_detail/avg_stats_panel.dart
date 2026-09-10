import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/shimmer.dart';
import '../../providers/avg_stats_provider.dart';
import 'avg_stats_logic.dart';

class AvgStatsPanel extends ConsumerWidget {
  const AvgStatsPanel({super.key, required this.snapshotId, this.champion});

  final int     snapshotId;
  final String? champion;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final payloadAsync = ref.watch(
      avgStatsPayloadProvider(AvgStatsRequest(snapshotId: snapshotId, champion: champion)),
    );
    return payloadAsync.when(
      loading: () => const _AvgStatsSkeleton(),
      error: (_, _) => const Padding(
        padding: EdgeInsets.all(16),
        child: Text('Error', style: TextStyle(fontSize: 11, color: kMuted)),
      ),
      data: (payload) {
        if (payload.matchCount == 0 || payload.metrics.isEmpty) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Text('No games', style: TextStyle(color: kMuted, fontSize: 11)),
            ),
          );
        }
        return ScrollConfiguration(
          behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
          child: ListView.builder(
            padding: const EdgeInsets.fromLTRB(8, 10, 8, 10),
            itemCount: payload.metrics.length,
            itemBuilder: (context, idx) {
              final m = payload.metrics[idx];
              return RepaintBoundary(
                child: StatCard(
                  label: m.label,
                  value: m.value,
                  status: m.status,
                  sparkData: m.sparkData,
                ),
              );
            },
          ),
        );
      },
    );
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _AvgStatsSkeleton extends StatelessWidget {
  const _AvgStatsSkeleton();

  @override
  Widget build(BuildContext context) {
    return Shimmer(
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(8, 10, 8, 10),
        itemCount: 10,
        separatorBuilder: (_, _) => const SizedBox(height: 8),
        itemBuilder: (_, _) => Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: kSurface2,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: kBorderColor.withValues(alpha: 0.35)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const ShimmerBox(width: 90, height: 10),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: const ShimmerBox(width: 52, height: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class StatCard extends StatelessWidget {
  const StatCard({
    super.key,
    required this.label,
    required this.value,
    this.sparkData,
    this.status = 'normal',
  });
  final String        label;
  final String        value;
  final List<double>? sparkData;
  final String        status;

  @override
  Widget build(BuildContext context) {
    final statusColor = getStatColor(label, status);
    final isLongValue = value.length > 12;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: kSurface2,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: kBorderColor.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 10,
              letterSpacing: 0.6,
              height: 1.3,
              color: kForeground,
              fontWeight: FontWeight.w600,
            ),
            maxLines: 3,
            softWrap: true,
          ),
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerRight,
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: TextStyle(
                fontSize: isLongValue ? 12 : 14,
                color: statusColor,
                fontWeight: FontWeight.bold,
                height: 1.1,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class Sparkline extends StatelessWidget {
  const Sparkline({super.key, required this.data});
  final List<double> data;

  @override
  Widget build(BuildContext context) {
    final spots = data.asMap().entries
        .map((e) => FlSpot(e.key.toDouble(), e.value))
        .toList();

    return LineChart(
      LineChartData(
        gridData:     const FlGridData(show: false),
        titlesData:   const FlTitlesData(show: false),
        borderData:   FlBorderData(show: false),
        lineTouchData: const LineTouchData(enabled: false),
        lineBarsData: [
          LineChartBarData(
            spots:    spots,
            isCurved: true,
            color:    kPrimary,
            barWidth: 1.5,
            dotData:  const FlDotData(show: false),
            belowBarData: BarAreaData(
              show:  true,
              color: kPrimary.withValues(alpha: 0.12),
            ),
          ),
        ],
      ),
    );
  }
}
