import 'dart:math' as math;
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/shimmer.dart';
import '../models/admin_stats_model.dart';
import '../providers/admin_provider.dart';

const _tierOrder = [
  'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM',
  'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER',
];

const _tierColors = {
  'IRON':        Color(0xFF6B7280), // gris oscuro
  'BRONZE':      Color(0xFFCD7F32), // bronce cobre
  'SILVER':      Color(0xFFA8B4BE), // gris plateado
  'GOLD':        Color(0xFFFFCC00), // dorado saturado
  'PLATINUM':    Color(0xFF35C2B8), // teal
  'EMERALD':     Color(0xFF3DBA6A), // verde esmeralda
  'DIAMOND':     Color(0xFF5B8DEF), // azul diamante
  'MASTER':      Color(0xFFAA44EE), // morado
  'GRANDMASTER': Color(0xFFE84040), // rojo
  'CHALLENGER':  Color(0xFF00D4FF), // cian brillante
};

class _ChartEntry {
  const _ChartEntry({required this.label, required this.value, required this.color});
  final String label;
  final int    value;
  final Color  color;
}

// ── Widget raíz ───────────────────────────────────────────────────────────────

class AdminStats extends ConsumerWidget {
  const AdminStats({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final statsAsync = ref.watch(adminStatsProvider);
    return statsAsync.when(
      loading: () => const _AdminStatsSkeleton(),
      error: (err, _) => Center(
        child: Text(err.toString(), style: const TextStyle(color: kMuted, fontSize: 13)),
      ),
      data: (stats) => _StatsContent(stats: stats),
    );
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _AdminStatsSkeleton extends StatelessWidget {
  const _AdminStatsSkeleton();

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Shimmer(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (narrow) ...[
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  Expanded(child: _StatCardSkeleton()),
                  SizedBox(width: 10),
                  Expanded(child: _StatCardSkeleton()),
                ],
              ),
            ),
            const SizedBox(height: 10),
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  Expanded(child: _StatCardSkeleton()),
                  SizedBox(width: 10),
                  Expanded(child: _StatCardSkeleton()),
                ],
              ),
            ),
            const SizedBox(height: 20),
            const _ChartPanelSkeleton(),
            const SizedBox(height: 16),
            const _ChartPanelSkeleton(),
            const SizedBox(height: 16),
            const _ChartPanelSkeleton(),
          ] else ...[
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  Expanded(child: _StatCardSkeleton()),
                  SizedBox(width: 12),
                  Expanded(child: _StatCardSkeleton()),
                  SizedBox(width: 12),
                  Expanded(child: _StatCardSkeleton()),
                  SizedBox(width: 12),
                  Expanded(child: _StatCardSkeleton()),
                ],
              ),
            ),
            const SizedBox(height: 20),
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  Expanded(child: _ChartPanelSkeleton()),
                  SizedBox(width: 16),
                  Expanded(child: _ChartPanelSkeleton()),
                  SizedBox(width: 16),
                  Expanded(child: _ChartPanelSkeleton()),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StatCardSkeleton extends StatelessWidget {
  const _StatCardSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: Row(
        children: const [
          ShimmerBox(width: 40, height: 40, radius: 8),
          SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                ShimmerBox(width: 56, height: 22),
                SizedBox(height: 6),
                ShimmerBox(width: 80, height: 11),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ChartPanelSkeleton extends StatelessWidget {
  const _ChartPanelSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      constraints: const BoxConstraints(minHeight: 220),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: const [
          ShimmerBox(width: 140, height: 10),
          SizedBox(height: 20),
          Center(child: ShimmerBox(width: 160, height: 160, radius: 80)),
        ],
      ),
    );
  }
}

// ── Contenido ─────────────────────────────────────────────────────────────────

class _StatsContent extends StatelessWidget {
  const _StatsContent({required this.stats});
  final AdminStatsModel stats;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;

    // Tier entries ordenados por _tierOrder
    final tierMap = {for (final t in stats.tierDistribution) t.tier.toUpperCase(): t.count};
    final tierEntries = _tierOrder
        .where((t) => tierMap.containsKey(t))
        .map((t) => _ChartEntry(
              label: t[0] + t.substring(1).toLowerCase(),
              value: tierMap[t]!,
              color: _tierColors[t] ?? kMuted,
            ))
        .toList();

    // Region entries
    final regionEntries = stats.regionDistribution
        .map((r) => _ChartEntry(label: r.region, value: r.count, color: kPrimary))
        .toList();

    final card1 = _StatCard(
      icon: Icons.people_outline,
      label: 'Users',
      value: '${stats.totalUsers}',
      badgeText: stats.inactiveUsers > 0 ? '${stats.inactiveUsers} inactive' : null,
    );
    final card2 = _StatCard(icon: Icons.manage_search_outlined, label: 'Players',          value: '${stats.totalPlayers}');
    final card3 = _StatCard(icon: Icons.history_outlined,       label: 'Snapshots',        value: '${stats.totalSnapshots}');
    final card4 = _StatCard(icon: Icons.sports_esports_outlined, label: 'Matches analysed', value: '${stats.totalMatches}');

    final panel1 = _ChartPanel(
      title: 'Rank Distribution',
      child: tierEntries.isEmpty ? const _EmptyChart() : _DonutChart(entries: tierEntries),
    );
    final panel2 = _ChartPanel(
      title: 'Players by Region',
      child: regionEntries.isEmpty ? const _EmptyChart() : _VerticalBarChart(entries: regionEntries),
    );
    final panel3 = _ChartPanel(
      title: 'Top Users',
      child: stats.topUsers.isEmpty ? const _EmptyChart() : _TopUsersList(users: stats.topUsers),
    );

    if (narrow) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 2×2 grid de cards
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [Expanded(child: card1), const SizedBox(width: 10), Expanded(child: card2)],
            ),
          ),
          const SizedBox(height: 10),
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [Expanded(child: card3), const SizedBox(width: 10), Expanded(child: card4)],
            ),
          ),
          const SizedBox(height: 20),
          // Paneles apilados verticalmente
          panel1,
          const SizedBox(height: 16),
          panel2,
          const SizedBox(height: 16),
          panel3,
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── 4 cards métricas globales ────────────────────────────────────
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(child: card1),
              const SizedBox(width: 12),
              Expanded(child: card2),
              const SizedBox(width: 12),
              Expanded(child: card3),
              const SizedBox(width: 12),
              Expanded(child: card4),
            ],
          ),
        ),
        const SizedBox(height: 20),
        // ── Gráficos ─────────────────────────────────────────────────────
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(child: panel1),
              const SizedBox(width: 16),
              Expanded(child: panel2),
              const SizedBox(width: 16),
              Expanded(child: panel3),
            ],
          ),
        ),
      ],
    );
  }
}

// ── Tarjeta de estadística ────────────────────────────────────────────────────

class _StatCard extends StatelessWidget {
  const _StatCard({required this.icon, required this.label, required this.value, this.badgeText});
  final IconData icon;
  final String   label;
  final String   value;
  final String?  badgeText;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: Row(
        children: [
          Container(
            width: 40, height: 40,
            decoration: BoxDecoration(
              color: kPrimary.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 20, color: kPrimary),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Flexible(
                      child: Text(value,
                        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: kForeground),
                        overflow: TextOverflow.ellipsis),
                    ),
                    if (badgeText != null) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.redAccent.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: Colors.redAccent.withValues(alpha: 0.3)),
                        ),
                        child: Text(badgeText!,
                          style: const TextStyle(fontSize: 10, color: Colors.redAccent)),
                      ),
                    ],
                  ],
                ),
                Text(label,
                  style: const TextStyle(fontSize: 11, color: kMuted),
                  overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Panel contenedor de gráfico ───────────────────────────────────────────────

class _ChartPanel extends StatelessWidget {
  const _ChartPanel({required this.title, required this.child});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title.toUpperCase(),
            style: const TextStyle(fontSize: 10, letterSpacing: 1.5, color: kMuted, fontWeight: FontWeight.w600)),
          const SizedBox(height: 20),
          child,
        ],
      ),
    );
  }
}

// ── Lista top usuarios ────────────────────────────────────────────────────────

class _TopUsersList extends StatelessWidget {
  const _TopUsersList({required this.users});
  final List<TopUser> users;

  static const _rankColors = [
    Color(0xFFFFD700), // #1 oro
    Color(0xFFC0C0C0), // #2 plata
    Color(0xFFCD7F32), // #3 bronce
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(users.length, (i) {
        final u = users[i];
        final rankColor = i < 3 ? _rankColors[i] : kMuted;
        final initial = u.username.isNotEmpty ? u.username[0].toUpperCase() : '?';

        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Row(
            children: [
              // Posición
              SizedBox(
                width: 26,
                child: Text('#${i + 1}',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: rankColor,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Avatar
              Container(
                width: 28, height: 28,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [kPrimary, kPrimary.withValues(alpha: 0.5)],
                  ),
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text(initial,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              // Nombre
              Expanded(
                child: Text(u.username,
                  style: const TextStyle(fontSize: 12, color: kForeground),
                  overflow: TextOverflow.ellipsis),
              ),
              // Badge jugadores
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: kPrimary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: kPrimary.withValues(alpha: 0.25)),
                ),
                child: Text('${u.playerCount} pl.',
                  style: const TextStyle(fontSize: 10, color: kPrimaryLight)),
              ),
            ],
          ),
        );
      }),
    );
  }
}

// ── Donut chart ───────────────────────────────────────────────────────────────

class _DonutChart extends StatefulWidget {
  const _DonutChart({required this.entries});
  final List<_ChartEntry> entries;

  @override
  State<_DonutChart> createState() => _DonutChartState();
}

class _DonutChartState extends State<_DonutChart> {
  int _touched = -1;

  @override
  Widget build(BuildContext context) {
    final total = widget.entries.fold(0, (s, e) => s + e.value);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        SizedBox(
          width: 140,
          height: 140,
          child: Stack(
            alignment: Alignment.center,
            children: [
              PieChart(
                PieChartData(
                  centerSpaceRadius: 44,
                  sectionsSpace: 2,
                  pieTouchData: PieTouchData(
                    touchCallback: (event, response) {
                      setState(() {
                        if (!event.isInterestedForInteractions ||
                            response == null ||
                            response.touchedSection == null) {
                          _touched = -1;
                        } else {
                          _touched = response.touchedSection!.touchedSectionIndex;
                        }
                      });
                    },
                  ),
                  sections: List.generate(widget.entries.length, (i) {
                    final e = widget.entries[i];
                    final isTouched = i == _touched;
                    return PieChartSectionData(
                      value: e.value.toDouble(),
                      color: e.color,
                      radius: isTouched ? 38 : 30,
                      title: isTouched ? '${e.value}' : '',
                      titleStyle: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    );
                  }),
                ),
                duration: const Duration(milliseconds: 500),
                curve: Curves.easeOutCubic,
              ),
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('$total',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: kForeground)),
                  const Text('players', style: TextStyle(fontSize: 9, color: kMuted)),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(width: 20),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: widget.entries.map((e) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                children: [
                  Container(
                    width: 9, height: 9,
                    decoration: BoxDecoration(color: e.color, borderRadius: BorderRadius.circular(3)),
                  ),
                  const SizedBox(width: 7),
                  Expanded(
                    child: Text(e.label,
                      style: const TextStyle(fontSize: 11, color: kForeground),
                      overflow: TextOverflow.ellipsis),
                  ),
                  Text('${e.value}', style: const TextStyle(fontSize: 11, color: kMuted)),
                ],
              ),
            )).toList(),
          ),
        ),
      ],
    );
  }
}

// ── Gráfico de barras verticales ──────────────────────────────────────────────

class _VerticalBarChart extends StatelessWidget {
  const _VerticalBarChart({required this.entries});
  final List<_ChartEntry> entries;

  @override
  Widget build(BuildContext context) {
    final maxVal = entries.map((e) => e.value).reduce(math.max).toDouble();
    return SizedBox(
      height: 184,
      child: BarChart(
        BarChartData(
          maxY: maxVal * 1.25,
          barGroups: List.generate(entries.length, (i) {
            final e = entries[i];
            return BarChartGroupData(
              x: i,
              barRods: [
                BarChartRodData(
                  toY: e.value.toDouble(),
                  gradient: LinearGradient(
                    colors: [kPrimary, kPrimaryLight.withValues(alpha: 0.8)],
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                  ),
                  width: 22,
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(5)),
                  backDrawRodData: BackgroundBarChartRodData(
                    show: true,
                    toY: maxVal * 1.25,
                    color: kSurface2.withValues(alpha: 0.35),
                  ),
                ),
              ],
            );
          }),
          titlesData: FlTitlesData(
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 32,
                getTitlesWidget: (value, _) {
                  final i = value.toInt();
                  if (i < 0 || i >= entries.length) return const SizedBox();
                  return Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      entries[i].label,
                      style: const TextStyle(fontSize: 10, color: kMuted),
                      overflow: TextOverflow.ellipsis,
                    ),
                  );
                },
              ),
            ),
            leftTitles:   const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            topTitles:    const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles:  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            getDrawingHorizontalLine: (_) => FlLine(
              color: kBorderColor.withValues(alpha: 0.25),
              strokeWidth: 1,
            ),
          ),
          borderData: FlBorderData(show: false),
          barTouchData: BarTouchData(
            touchTooltipData: BarTouchTooltipData(
              getTooltipColor: (_) => kSurface2,
              tooltipBorder: BorderSide(color: kPrimary.withValues(alpha: 0.3)),
              getTooltipItem: (group, groupIndex, rod, rodIndex) => BarTooltipItem(
                '${entries[group.x].label}\n',
                const TextStyle(color: kMuted, fontSize: 10),
                children: [
                  TextSpan(
                    text: '${rod.toY.toInt()}',
                    style: const TextStyle(
                      color: kForeground,
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        duration: const Duration(milliseconds: 600),
        curve: Curves.easeOutCubic,
      ),
    );
  }
}

// ── Sin datos ─────────────────────────────────────────────────────────────────

class _EmptyChart extends StatelessWidget {
  const _EmptyChart();

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.symmetric(vertical: 40),
    child: Center(child: Text('No data', style: TextStyle(color: kMuted, fontSize: 13))),
  );
}
