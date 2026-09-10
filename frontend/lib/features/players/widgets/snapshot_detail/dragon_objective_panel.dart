import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/match_model.dart';
import '../../providers/match_provider.dart';
import 'chart_shared_widgets.dart';

// ── Dragon type colours ───────────────────────────────────────────────────────

const _kDragonColors = <String, Color>{
  'FIRE_DRAGON':     Color(0xFFFF6B35),
  'WATER_DRAGON':    Color(0xFF4EA8DE),
  'EARTH_DRAGON':    Color(0xFFA0785A),
  'AIR_DRAGON':      Color(0xFFB0C4D8),
  'HEXTECH_DRAGON':  Color(0xFF00E5CC),
  'CHEMTECH_DRAGON': Color(0xFF7FBA00),
  'ELDER_DRAGON':    Color(0xFFFFD700),
};

Color _dragonColor(String type) =>
    _kDragonColors[type.toUpperCase()] ?? kMuted;

String _dragonLabel(String type) =>
    type.toUpperCase().replaceAll('_DRAGON', '');

// ── Panel principal ───────────────────────────────────────────────────────────

class DragonObjectivePanel extends ConsumerWidget {
  const DragonObjectivePanel({
    super.key,
    required this.snapshotId,
    this.champion,
  });

  final int     snapshotId;
  final String? champion;

  List<MatchModel> _filter(List<MatchModel> all) =>
      champion != null ? all.where((m) => m.champion == champion).toList() : all;

  Color _rateColor(double? rate) {
    if (rate == null) return kMuted;
    if (rate >= 60) return kStatGold;
    if (rate >= 50) return kStatBlue;
    if (rate >= 40) return kStatGreen;
    return kStatGray;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final narrow = MediaQuery.of(context).size.width < 600;
    final matchesAsync = ref.watch(snapshotMatchesProvider(snapshotId));

    return matchesAsync.when(
      loading: () => const ChartCard(
        title: 'Dragon Objective Control',
        subtitle: 'Loading dragon setup data...',
        child: SizedBox(
          height: 100,
          child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: kPrimary)),
        ),
      ),
      error: (e, _) => const ChartCard(
        title: 'Dragon Objective Control',
        subtitle: 'Could not load match data',
        child: SizedBox(height: 60),
      ),
      data: (allMatches) {
        final matches     = _filter(allMatches);
        final teamDragons = matches.expand((m) => m.teamDragonSetups).toList();

        if (teamDragons.isEmpty) {
          return const ChartCard(
            title: 'Dragon Objective Control',
            subtitle: 'Setup = in pit zone 90s before kill · At kill = present at dragon death',
            child: Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Text(
                'No team dragon data in filtered games. Refresh snapshots to backfill.',
                style: TextStyle(fontSize: 11, color: kMuted),
              ),
            ),
          );
        }

        // ── Aggregate summary stats ─────────────────────────────────────
        final setupRates    = matches.map((m) => m.dragonSetupRate).whereType<double>().toList();
        final avgSetup      = setupRates.isEmpty    ? null : setupRates.reduce((a, b) => a + b)    / setupRates.length;
        final presenceRates = matches.map((m) => m.dragonPresenceRate).whereType<double>().toList();
        final avgPresence   = presenceRates.isEmpty ? null : presenceRates.reduce((a, b) => a + b) / presenceRates.length;
        final secureRates   = matches.map((m) => m.dragonSecureRate).whereType<double>().toList();
        final avgSecure     = secureRates.isEmpty   ? null : secureRates.reduce((a, b) => a + b)   / secureRates.length;
        final firstDragonCount = matches.where((m) => m.firstDragon).length;
        final firstDragonRate  = matches.isEmpty ? null : firstDragonCount / matches.length * 100;

        // ── Dragon type breakdown ───────────────────────────────────────
        final Map<String, ({int total, int good, int contested, int secured, int totalTime})> typeStats = {};
        for (final setup in teamDragons) {
          final type = setup.dragonType.toUpperCase();
          if (type == 'UNKNOWN') continue;
          final prev   = typeStats[type] ?? (total: 0, good: 0, contested: 0, secured: 0, totalTime: 0);
          final isGood = setup.inPrepZone && setup.atKillZone;
          typeStats[type] = (
            total:     prev.total     + 1,
            good:      prev.good      + (isGood             ? 1 : 0),
            contested: prev.contested + (setup.contested     ? 1 : 0),
            secured:   prev.secured   + (setup.securedByJg   ? 1 : 0),
            totalTime: prev.totalTime + setup.dragonTime,
          );
        }
        final sortedTypes = typeStats.entries.toList()
          ..sort((a, b) => b.value.total.compareTo(a.value.total));

        // ── Per-match summary (last 8) ──────────────────────────────────
        final displayMatches = matches.length > 8
            ? matches.sublist(matches.length - 8)
            : matches;

        return ChartCard(
          title: 'Dragon Objective Control',
          subtitle: 'Setup = in pit zone 90s before kill · At kill = present at dragon death',
          onFullscreen: narrow && !chartIsInFullscreen(context)
              ? () => FullscreenChartScreen.push(
                    context,
                    DragonObjectivePanel(snapshotId: snapshotId, champion: champion),
                  )
              : null,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [

              // ── Summary chips ───────────────────────────────────────
              Wrap(
                alignment: WrapAlignment.center,
                spacing: 12,
                runSpacing: 12,
                children: [
                  _StatChip(label: 'Team dragons', value: '${teamDragons.length}',                                                          color: kForeground,            rate: null),
                  _StatChip(label: 'Setup rate',   value: avgSetup    != null ? '${avgSetup.toStringAsFixed(0)}%'    : '—',                  color: _rateColor(avgSetup),   rate: avgSetup),
                  _StatChip(label: 'At kill',      value: avgPresence != null ? '${avgPresence.toStringAsFixed(0)}%' : '—',                  color: _rateColor(avgPresence),rate: avgPresence),
                  _StatChip(label: 'Secured',      value: avgSecure   != null ? '${avgSecure.toStringAsFixed(0)}%'   : '—',                  color: _rateColor(avgSecure),  rate: avgSecure),
                  _StatChip(label: 'First dragon', value: firstDragonRate != null ? '$firstDragonCount / ${matches.length}' : '—',           color: _rateColor(firstDragonRate), rate: firstDragonRate),
                ],
              ),

              const SizedBox(height: 24),
              const _GradientDivider(),

              // ── Dragon type breakdown ───────────────────────────────
              const SizedBox(height: 18),
              const _SectionLabel(label: 'DRAGON TYPE BREAKDOWN'),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: Wrap(
                  spacing:    8,
                  runSpacing: 8,
                  alignment:  WrapAlignment.center,
                  children: sortedTypes
                      .map((e) => _DragonTypeGridCard(
                            dragonType:     e.key,
                            total:          e.value.total,
                            goodCount:      e.value.good,
                            contestedCount: e.value.contested,
                            securedCount:   e.value.secured,
                            avgMinutes:     e.value.totalTime > 0
                                ? e.value.totalTime / e.value.total / 60
                                : null,
                          ))
                      .toList(),
                ),
              ),

              const SizedBox(height: 24),
              const _GradientDivider(),

              // ── Per-match summary ───────────────────────────────────
              const SizedBox(height: 18),
              const _SectionLabel(label: 'BY MATCH  ·  LAST 8 GAMES'),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: const [
                  _LegendDot(color: kStatGreen, label: 'Perfect'),
                  SizedBox(width: 10),
                  _LegendDot(color: kStatBlue,  label: 'Partial'),
                  SizedBox(width: 10),
                  _LegendDot(color: kStatGray,  label: 'Missed'),
                  SizedBox(width: 10),
                  _ContestedLegend(),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: Wrap(
                  spacing:    8,
                  runSpacing: 8,
                  alignment:  WrapAlignment.center,
                  children: displayMatches.asMap().entries
                      .map((e) => _MatchGridCard(index: e.key + 1, match: e.value))
                      .toList(),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ── Section helpers ───────────────────────────────────────────────────────────

class _GradientDivider extends StatelessWidget {
  const _GradientDivider();
  @override
  Widget build(BuildContext context) => Container(
    height: 1,
    decoration: BoxDecoration(
      gradient: LinearGradient(colors: [
        kPrimary.withValues(alpha: 0.35),
        kBorderColor.withValues(alpha: 0.15),
        Colors.transparent,
      ]),
    ),
  );
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.label});
  final String label;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 3,
        height: 13,
        decoration: BoxDecoration(
          color: kPrimary.withValues(alpha: 0.7),
          borderRadius: BorderRadius.circular(2),
        ),
      ),
      const SizedBox(width: 8),
      Text(
        label,
        style: const TextStyle(
          fontSize: 10,
          color: kForeground,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.4,
        ),
      ),
    ],
  );
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});
  final Color  color;
  final String label;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 9, height: 9,
        decoration: BoxDecoration(
          shape:  BoxShape.circle,
          color:  color.withValues(alpha: 0.25),
          border: Border.all(color: color.withValues(alpha: 0.90), width: 1.5),
        ),
      ),
      const SizedBox(width: 5),
      Text(label, style: const TextStyle(fontSize: 9, color: kMuted)),
    ],
  );
}

class _ContestedLegend extends StatelessWidget {
  const _ContestedLegend();
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 11, height: 11,
        decoration: BoxDecoration(
          shape:  BoxShape.circle,
          border: Border.all(color: kStatGold.withValues(alpha: 0.70), width: 1.0),
        ),
        child: Center(
          child: Container(
            width: 7, height: 7,
            decoration: BoxDecoration(color: kMuted.withValues(alpha: 0.4), shape: BoxShape.circle),
          ),
        ),
      ),
      const SizedBox(width: 5),
      const Text('Contested', style: TextStyle(fontSize: 9, color: kMuted)),
    ],
  );
}

// ── Dragon type grid card ─────────────────────────────────────────────────────

class _DragonTypeGridCard extends StatelessWidget {
  const _DragonTypeGridCard({
    required this.dragonType,
    required this.total,
    required this.goodCount,
    required this.contestedCount,
    required this.securedCount,
    required this.avgMinutes,
  });

  final String  dragonType;
  final int     total;
  final int     goodCount;
  final int     contestedCount;
  final int     securedCount;
  final double? avgMinutes;

  @override
  Widget build(BuildContext context) {
    final rate  = total > 0 ? goodCount / total : 0.0;
    final color = _dragonColor(dragonType);
    final label = _dragonLabel(dragonType);

    return Container(
      width:  102,
      height: 150,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color:        color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(10),
        border:       Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [

          // ── Coloured top strip ─────────────────────────────
          Container(height: 4, color: color.withValues(alpha: 0.80)),

          // ── Content ────────────────────────────────────────
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: color,
                      letterSpacing: 0.8,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${(rate * 100).toStringAsFixed(0)}%',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: color,
                      height: 1.0,
                    ),
                  ),
                  Text(
                    'perfect',
                    style: TextStyle(fontSize: 9, color: kMuted, letterSpacing: 0.5),
                  ),
                  const SizedBox(height: 8),
                  TweenAnimationBuilder<double>(
                    duration: const Duration(milliseconds: 700),
                    curve: Curves.easeOutCubic,
                    tween: Tween(begin: 0, end: rate.clamp(0.0, 1.0)),
                    builder: (_, v, _) => ClipRRect(
                      borderRadius: BorderRadius.circular(3),
                      child: LinearProgressIndicator(
                        value:           v,
                        minHeight:       4,
                        backgroundColor: color.withValues(alpha: 0.14),
                        valueColor:      AlwaysStoppedAnimation<Color>(color.withValues(alpha: 0.85)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '$total ${total == 1 ? 'game' : 'games'}',
                    style: const TextStyle(fontSize: 9, color: kMuted),
                    textAlign: TextAlign.center,
                  ),
                  if (contestedCount > 0) ...[
                    const SizedBox(height: 3),
                    Text(
                      '$contestedCount contested',
                      style: TextStyle(fontSize: 8, color: kStatGold.withValues(alpha: 0.80)),
                      textAlign: TextAlign.center,
                    ),
                  ],
                  if (securedCount > 0) ...[
                    const SizedBox(height: 3),
                    Text(
                      '$securedCount JG secured',
                      style: TextStyle(fontSize: 8, color: kStatBlue.withValues(alpha: 0.85)),
                      textAlign: TextAlign.center,
                    ),
                  ],
                  if (avgMinutes != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      'avg ~${avgMinutes!.toStringAsFixed(0)}m',
                      style: const TextStyle(fontSize: 8, color: kMuted),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Per-match grid card ───────────────────────────────────────────────────────

class _MatchGridCard extends StatelessWidget {
  const _MatchGridCard({required this.index, required this.match});
  final int        index;
  final MatchModel match;

  @override
  Widget build(BuildContext context) {
    final setups   = match.teamDragonSetups;
    final good     = setups.where((s) => s.inPrepZone && s.atKillZone).length;
    final total    = setups.length;
    final winColor = match.win ? kStatGreen : kStatRed;

    final scoreColor = total == 0
        ? kMuted
        : good == total
            ? kStatGold
            : good > 0
                ? kStatGreen
                : kStatGray;

    final dots = setups.map((s) {
      final color     = _dragonColor(s.dragonType);
      final isPerfect = s.inPrepZone && s.atKillZone;
      final isPartial = s.inPrepZone && !s.atKillZone;
      final fill      = isPerfect ? 0.75 : isPartial ? 0.30 : 0.08;
      final qualColor = isPerfect ? kStatGreen : isPartial ? kStatBlue : kStatGray;
      final quality   = isPerfect ? 'Perfect setup' : isPartial ? 'Partial setup' : 'Missed setup';

      // Outer container always 17×17 → todos los dots tienen la misma altura
      return Tooltip(
        richMessage: TextSpan(children: [
          TextSpan(
            text: '${_dragonLabel(s.dragonType)}\n',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          TextSpan(
            text: quality,
            style: TextStyle(fontSize: 10, color: qualColor),
          ),
          if (s.contested)
            TextSpan(
              text: '  ·  Contested',
              style: TextStyle(fontSize: 10, color: kStatGold.withValues(alpha: 0.85)),
            ),
        ]),
        decoration: BoxDecoration(
          color:        kSurface2,
          borderRadius: BorderRadius.circular(8),
          border:       Border.all(color: kPrimary.withValues(alpha: 0.28)),
          boxShadow: [
            BoxShadow(
              color:      Colors.black.withValues(alpha: 0.35),
              blurRadius: 10,
              offset:     const Offset(0, 3),
            ),
          ],
        ),
        textAlign:    TextAlign.center,
        padding:      const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        preferBelow:  false,
        waitDuration: const Duration(milliseconds: 300),
        child: Container(
          width: 17, height: 17,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape:  BoxShape.circle,
            border: s.contested
                ? Border.all(color: kStatGold.withValues(alpha: 0.70), width: 1.0)
                : null,
          ),
          child: Container(
            width: 13, height: 13,
            decoration: BoxDecoration(
              shape:  BoxShape.circle,
              color:  color.withValues(alpha: fill),
              border: Border.all(color: qualColor.withValues(alpha: 0.90), width: 1.5),
            ),
          ),
        ),
      );
    }).toList();

    return Container(
      width:  102,
      height: 150,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color:        kSurface2,
        borderRadius: BorderRadius.circular(10),
        border:       Border.all(color: winColor.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [

          // ── W/L coloured top strip ─────────────────────────
          Container(height: 4, color: winColor.withValues(alpha: 0.80)),

          // ── Content (fixed-height rows so all cards align) ─
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 9),
            child: Column(
              mainAxisSize:        MainAxisSize.min,
              crossAxisAlignment:  CrossAxisAlignment.center,
              children: [

                // row 1 – G# + WIN/LOSS  (h = 14)
                SizedBox(
                  height: 14,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text('G$index',
                          style: const TextStyle(fontSize: 9, color: kMuted, fontWeight: FontWeight.w500)),
                      const SizedBox(width: 5),
                      Text(match.win ? 'WIN' : 'LOSS',
                          style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold,
                              color: winColor, letterSpacing: 0.5)),
                    ],
                  ),
                ),
                const SizedBox(height: 4),

                // row 2 – champion name  (h = 15)
                SizedBox(
                  height: 15,
                  child: Text(
                    match.champion,
                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: kForeground),
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(height: 5),

                // row 3 – dragon dots  (h = 38 = 2 rows de 17px + 4px runSpacing)
                SizedBox(
                  height: 38,
                  child: setups.isEmpty
                      ? const Center(child: Text('—', style: TextStyle(fontSize: 10, color: kMuted)))
                      : Wrap(
                          spacing:    4,
                          runSpacing: 4,
                          alignment:  WrapAlignment.center,
                          children:   dots,
                        ),
                ),
                const SizedBox(height: 5),

                // row 4 – score  (h = 20)
                SizedBox(
                  height: 20,
                  child: total > 0
                      ? Center(
                          child: RichText(
                            text: TextSpan(children: [
                              TextSpan(
                                text: '$good',
                                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: scoreColor),
                              ),
                              TextSpan(
                                text: '/$total',
                                style: const TextStyle(fontSize: 10, color: kMuted),
                              ),
                            ]),
                          ),
                        )
                      : const SizedBox.shrink(),
                ),
                const SizedBox(height: 5),

                // row 5 – first dragon badge  (h = 16, always reserved)
                SizedBox(
                  height: 16,
                  child: match.firstDragon
                      ? Center(
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                            decoration: BoxDecoration(
                              color:        kStatGold.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(6),
                              border:       Border.all(color: kStatGold.withValues(alpha: 0.55)),
                            ),
                            child: const Text(
                              'FIRST DRAGON',
                              style: TextStyle(
                                fontSize: 7,
                                fontWeight: FontWeight.bold,
                                color: kStatGold,
                                letterSpacing: 0.7,
                              ),
                            ),
                          ),
                        )
                      : const SizedBox.shrink(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Stat chip (summary) ───────────────────────────────────────────────────────

class _StatChip extends StatelessWidget {
  const _StatChip({
    required this.label,
    required this.value,
    required this.color,
    required this.rate,
  });

  final String  label;
  final String  value;
  final Color   color;
  final double? rate;

  @override
  Widget build(BuildContext context) {
    return Container(
      width:   90,
      height:  82,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color:        kSurface2,
        borderRadius: BorderRadius.circular(8),
        border:       Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        mainAxisSize:      MainAxisSize.max,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            height: 14,
            child: Center(
              child: Text(
                label,
                style: const TextStyle(fontSize: 9, color: kMuted, letterSpacing: 0.4),
                textAlign: TextAlign.center,
              ),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color),
          ),
          const SizedBox(height: 6),
          SizedBox(
            height: 3,
            child: rate != null
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(2),
                    child: LinearProgressIndicator(
                      value:           (rate! / 100).clamp(0.0, 1.0),
                      minHeight:       3,
                      backgroundColor: color.withValues(alpha: 0.15),
                      valueColor:      AlwaysStoppedAnimation<Color>(color),
                    ),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }
}
