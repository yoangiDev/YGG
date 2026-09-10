import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../features/players/providers/rank_cutoffs_provider.dart';
import '../features/players/widgets/hextech_header.dart';

class RankCutoffsScreen extends ConsumerStatefulWidget {
  const RankCutoffsScreen({super.key, this.initialRegion});

  final String? initialRegion;

  @override
  ConsumerState<RankCutoffsScreen> createState() => _RankCutoffsScreenState();
}

class _RankCutoffsScreenState extends ConsumerState<RankCutoffsScreen> {
  late String _selectedRegion;
  bool _loading = false;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _selectedRegion = widget.initialRegion?.toUpperCase() ?? 'EUW';
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadCutoffs(force: false);
      _refreshTimer = Timer.periodic(rankCutoffsRefreshInterval, (_) {
        if (mounted) _loadCutoffs(force: false);
      });
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadCutoffs({required bool force}) async {
    setState(() => _loading = true);
    await ref.read(rankCutoffsProvider.notifier).refreshRegion(
      _selectedRegion,
      force: force,
    );
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final cutoffsMap = ref.watch(rankCutoffsProvider);
    final cutoffs    = rankCutoffsForRegion(cutoffsMap, _selectedRegion);
    final notifier   = ref.read(rankCutoffsProvider.notifier);
    final size       = MediaQuery.sizeOf(context);
    final hPad       = (size.width * 0.04).clamp(16.0, 24.0);
    final vPad       = (size.height * 0.025).clamp(16.0, 28.0);
    final sectionGap = size.width < 520 ? 14.0 : 18.0;
    final isCompact  = size.width < 560;

    return Scaffold(
      backgroundColor: kBgColor,
      body: Column(
        children: [
          const HextechHeader(title: 'LP Cutoffs'),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                return SingleChildScrollView(
                  padding: EdgeInsets.fromLTRB(hPad, vPad * 0.5, hPad, vPad * 1.5),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minHeight: constraints.maxHeight - vPad * 2),
                    child: Align(
                      alignment: const Alignment(0, -0.3),
                      child: ConstrainedBox(
                        constraints: BoxConstraints(maxWidth: size.width.clamp(320.0, 720.0)),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            _ScreenHeader(
                              onBack: () => Navigator.of(context).pop(),
                              loading: _loading,
                              onRefresh: () => _loadCutoffs(force: true),
                            ),
                            SizedBox(height: sectionGap),
                            _RegionSelector(
                              selected: _selectedRegion,
                              regions: kSupportedRegions,
                              onChanged: (region) {
                                setState(() => _selectedRegion = region);
                                _loadCutoffs(force: false);
                              },
                            ),
                            SizedBox(height: sectionGap),
                            if (cutoffs != null) ...[
                              _UpdateInfo(
                                fetchedAt: cutoffs.fetchedAt,
                                nextRefreshAt: notifier.nextRefreshAt(cutoffs),
                                isStale: notifier.isStale(cutoffs),
                              ),
                              SizedBox(height: sectionGap + 4),
                            ],
                            if (_loading && cutoffs == null)
                              Padding(
                                padding: EdgeInsets.symmetric(vertical: size.height * 0.12),
                                child: const Center(
                                  child: CircularProgressIndicator(strokeWidth: 2, color: kPrimary),
                                ),
                              )
                            else if (cutoffs == null)
                              const _EmptyState()
                            else if (isCompact)
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  _CutoffCard(
                                    tier: 'GRANDMASTER',
                                    badgeAsset: 'assets/rank_badges/grandmaster_badge.png',
                                    barColor: const Color(0xFFE04030),
                                    rankLabel: 'Rank 1000 cutoff',
                                    lp: cutoffs.grandmasterCutoffLp,
                                    compact: true,
                                  ),
                                  SizedBox(height: sectionGap),
                                  _CutoffCard(
                                    tier: 'CHALLENGER',
                                    badgeAsset: 'assets/rank_badges/challenger_badge.png',
                                    barColor: const Color(0xFFF0D020),
                                    rankLabel: 'Rank 300 cutoff',
                                    lp: cutoffs.challengerCutoffLp,
                                    compact: true,
                                  ),
                                ],
                              )
                            else
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Expanded(
                                    child: _CutoffCard(
                                      tier: 'GRANDMASTER',
                                      badgeAsset: 'assets/rank_badges/grandmaster_badge.png',
                                      barColor: const Color(0xFFE04030),
                                      rankLabel: 'Rank 1000 cutoff',
                                      lp: cutoffs.grandmasterCutoffLp,
                                    ),
                                  ),
                                  SizedBox(width: sectionGap + 2),
                                  Expanded(
                                    child: _CutoffCard(
                                      tier: 'CHALLENGER',
                                      badgeAsset: 'assets/rank_badges/challenger_badge.png',
                                      barColor: const Color(0xFFF0D020),
                                      rankLabel: 'Rank 300 cutoff',
                                      lp: cutoffs.challengerCutoffLp,
                                    ),
                                  ),
                                ],
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ScreenHeader extends StatelessWidget {
  const _ScreenHeader({
    required this.onBack,
    required this.loading,
    required this.onRefresh,
  });

  final VoidCallback onBack;
  final bool loading;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Row(
      children: [
        if (!narrow) ...[
          IconButton(
            icon: const Icon(Icons.arrow_back_ios, size: 18, color: kMuted),
            onPressed: onBack,
            tooltip: 'Back',
          ),
          const SizedBox(width: 8),
        ],
        const Expanded(
          child: Text(
            'High Elo LP Cutoffs',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: kForeground,
            ),
          ),
        ),
        TextButton.icon(
          onPressed: loading ? null : onRefresh,
          icon: loading
              ? const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight),
                )
              : const Icon(Icons.refresh, size: 16, color: kPrimaryLight),
          label: const Text(
            'REFRESH',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.1,
              color: kPrimaryLight,
            ),
          ),
        ),
      ],
    );
  }
}

class _RegionSelector extends StatelessWidget {
  const _RegionSelector({
    required this.selected,
    required this.regions,
    required this.onChanged,
  });

  final String selected;
  final List<String> regions;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Region',
          style: TextStyle(color: kMuted, fontSize: 10, letterSpacing: 1.2),
        ),
        const SizedBox(height: 4),
        LayoutBuilder(
          builder: (_, constraints) => PopupMenuButton<String>(
            initialValue: selected,
            onSelected: onChanged,
            offset: const Offset(0, 40),
            color: kSurface2,
            constraints: BoxConstraints(
              minWidth: constraints.maxWidth,
              maxWidth: constraints.maxWidth,
              maxHeight: 260,
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
              side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
            ),
            itemBuilder: (_) => regions
                .map((r) => PopupMenuItem(
                      value: r,
                      child: Text(r,
                          style: const TextStyle(
                              color: kForeground, fontSize: 13)),
                    ))
                .toList(),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: kSurface2,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: kBorderColor),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(selected,
                      style: const TextStyle(
                          color: kForeground, fontSize: 13)),
                  const Icon(Icons.arrow_drop_down,
                      size: 18, color: kMuted),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _UpdateInfo extends StatelessWidget {
  const _UpdateInfo({
    required this.fetchedAt,
    required this.nextRefreshAt,
    required this.isStale,
  });

  final DateTime fetchedAt;
  final DateTime nextRefreshAt;
  final bool isStale;

  String _format(DateTime dt) {
    final local = dt.toLocal();
    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    return '${local.day}/${local.month}/${local.year} · $h:$m';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: kSurface2,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kBorderColor.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isStale ? Icons.schedule : Icons.check_circle_outline,
                size: 14,
                color: isStale ? kStatGold : kStatGreen,
              ),
              const SizedBox(width: 8),
              Text(
                'Last updated: ${_format(fetchedAt)}',
                style: const TextStyle(fontSize: 12, color: kForeground),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Auto-refresh every 4 hours · Next update: ${_format(nextRefreshAt)}',
            style: const TextStyle(fontSize: 11, color: kMuted),
          ),
        ],
      ),
    );
  }
}

class _CutoffCard extends StatelessWidget {
  const _CutoffCard({
    required this.tier,
    required this.badgeAsset,
    required this.barColor,
    required this.rankLabel,
    required this.lp,
    this.compact = false,
  });

  final String tier;
  final String badgeAsset;
  final Color barColor;
  final String rankLabel;
  final int lp;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final badgeSize = compact ? 72.0 : 88.0;
    final cardPad   = compact ? 18.0 : 20.0;

    return Container(
      padding: EdgeInsets.all(cardPad),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: barColor.withValues(alpha: 0.35)),
        boxShadow: [
          BoxShadow(
            color: barColor.withValues(alpha: 0.08),
            blurRadius: 24,
            spreadRadius: 1,
          ),
        ],
      ),
      child: Column(
        children: [
          Image.asset(badgeAsset, width: badgeSize, height: badgeSize),
          SizedBox(height: compact ? 12 : 16),
          Text(
            tier,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.4,
              color: barColor,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            rankLabel,
            style: const TextStyle(fontSize: 11, color: kMuted),
          ),
          const SizedBox(height: 20),
          Text(
            '$lp LP',
            style: const TextStyle(
              fontSize: 36,
              fontWeight: FontWeight.bold,
              color: kForeground,
              height: 1,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 64),
      child: Column(
        children: [
          Icon(Icons.cloud_off_outlined, size: 40, color: kMuted.withValues(alpha: 0.6)),
          const SizedBox(height: 12),
          const Text(
            'Cutoffs unavailable',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: kForeground),
          ),
          const SizedBox(height: 6),
          const Text(
            'Could not load data for this region. Try refreshing.',
            style: TextStyle(fontSize: 12, color: kMuted),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
