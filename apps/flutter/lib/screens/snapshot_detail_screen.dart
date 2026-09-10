import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../features/players/models/snapshot_model.dart';
import '../features/players/providers/ddragon_provider.dart';
import '../features/players/providers/match_provider.dart';
import '../features/players/providers/players_provider.dart';
import '../features/players/widgets/hextech_header.dart';
import '../features/players/widgets/snapshot_detail/avg_stats_panel.dart';
import '../features/players/widgets/snapshot_detail/champion_filter_column.dart';
import '../features/players/widgets/snapshot_detail/charts_area.dart';
import '../features/players/widgets/snapshot_detail/snapshot_detail_header.dart';
import '../features/players/widgets/snapshot_detail/snapshot_match_list.dart';

class SnapshotDetailScreen extends ConsumerStatefulWidget {
  const SnapshotDetailScreen({super.key, required this.snapshot});
  final SnapshotModel snapshot;

  @override
  ConsumerState<SnapshotDetailScreen> createState() => _SnapshotDetailScreenState();
}

class _SnapshotDetailScreenState extends ConsumerState<SnapshotDetailScreen> {
  late SnapshotModel _snapshot;
  String? _selectedChampion; // null = ALL
  final ScrollController _chartsScroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _snapshot = widget.snapshot;
  }

  @override
  void dispose() {
    _chartsScroll.dispose();
    super.dispose();
  }

  void _onSnapshotUpdated(SnapshotModel updated) {
    setState(() => _snapshot = updated);
  }

  void _onChampionSelected(String? champ) {
    setState(() => _selectedChampion = champ);
    // Vuelve al principio de las gráficas al cambiar el filtro
    if (_chartsScroll.hasClients) {
      _chartsScroll.jumpTo(0);
    }
  }

  @override
  Widget build(BuildContext context) {
    final player = ref.watch(playersProvider).valueOrNull
        ?.where((p) => p.id == _snapshot.playerId)
        .firstOrNull;

    return Scaffold(
      backgroundColor: kBgColor,
      body: Column(
        children: [
          const HextechHeader(title: 'Snapshot'),
          SnapshotDetailHeader(
            snapshot: _snapshot,
            onUpdated: _onSnapshotUpdated,
            player: player,
          ),
          Expanded(
            child: LayoutBuilder(builder: (context, constraints) {
              if (MediaQuery.of(context).size.shortestSide < 600) {
                // ── Móvil: 3 tabs + franja de filtro horizontal ──────────────
                return DefaultTabController(
                  length: 3,
                  child: Column(
                    children: [
                      TabBar(
                        labelColor: kPrimaryLight,
                        unselectedLabelColor: kMuted,
                        indicatorColor: kPrimary,
                        dividerColor: kBorderColor.withValues(alpha: 0.3),
                        labelStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
                        tabs: const [
                          Tab(text: 'STATS'),
                          Tab(text: 'CHARTS'),
                          Tab(text: 'MATCHES'),
                        ],
                      ),
                      _MobileChampionFilterRow(
                        snapshotId:       _snapshot.id,
                        selectedChampion: _selectedChampion,
                        onSelected:       _onChampionSelected,
                      ),
                      Expanded(
                        child: TabBarView(
                          children: [
                            AvgStatsPanel(snapshotId: _snapshot.id, champion: _selectedChampion),
                            SingleChildScrollView(
                              controller: _chartsScroll,
                              padding: const EdgeInsets.all(16),
                              child: ChartsArea(snapshotId: _snapshot.id, champion: _selectedChampion),
                            ),
                            SnapshotMatchList(snapshotId: _snapshot.id, champion: _selectedChampion),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }
              // ── Desktop: filtro + stats fijos | tabs charts/matches ───────
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 72,
                    decoration: BoxDecoration(
                      color: kSurfaceColor,
                      border: Border(
                        right: BorderSide(color: kBorderColor.withValues(alpha: 0.4)),
                      ),
                    ),
                    child: ChampionFilterColumn(
                      snapshotId:       _snapshot.id,
                      selectedChampion: _selectedChampion,
                      onSelected:       (champ) => setState(() => _selectedChampion = champ),
                    ),
                  ),
                  Container(
                    width: 310,
                    decoration: BoxDecoration(
                      color: kSurfaceColor,
                      border: Border(
                        right: BorderSide(color: kBorderColor.withValues(alpha: 0.4)),
                      ),
                    ),
                    child: AvgStatsPanel(snapshotId: _snapshot.id, champion: _selectedChampion),
                  ),
                  Expanded(
                    child: DefaultTabController(
                      length: 2,
                      child: Column(
                        children: [
                          TabBar(
                            labelColor: kPrimaryLight,
                            unselectedLabelColor: kMuted,
                            indicatorColor: kPrimary,
                            dividerColor: kBorderColor.withValues(alpha: 0.3),
                            labelStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
                            tabs: const [
                              Tab(text: 'CHARTS'),
                              Tab(text: 'MATCHES'),
                            ],
                          ),
                          Expanded(
                            child: TabBarView(
                              children: [
                                SingleChildScrollView(
                                  controller: _chartsScroll,
                                  padding: const EdgeInsets.all(24),
                                  child: ChartsArea(
                                    snapshotId: _snapshot.id,
                                    champion:   _selectedChampion,
                                  ),
                                ),
                                SnapshotMatchList(snapshotId: _snapshot.id, champion: _selectedChampion),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              );
            }),
          ),
        ],
      ),
    );
  }
}

// ── Franja horizontal de filtro por campeón (solo móvil) ─────────────────────

class _MobileChampionFilterRow extends ConsumerWidget {
  const _MobileChampionFilterRow({
    required this.snapshotId,
    required this.selectedChampion,
    required this.onSelected,
  });

  final int     snapshotId;
  final String? selectedChampion;
  final void Function(String?) onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final matchesAsync = ref.watch(snapshotMatchesProvider(snapshotId));
    final versionAsync = ref.watch(ddragonVersionProvider);

    return Container(
      height: 64,
      decoration: BoxDecoration(
        color: kSurfaceColor,
        border: Border(
          bottom: BorderSide(color: kBorderColor.withValues(alpha: 0.35)),
        ),
      ),
      child: matchesAsync.when(
        loading: () => const Center(
          child: SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight),
          ),
        ),
        error: (_, _) => const SizedBox.shrink(),
        data: (matches) {
          final champions = matches
              .map((m) => m.champion)
              .toSet()
              .toList()
            ..sort();
          final version = versionAsync.valueOrNull ?? '16.10.1';

          return ScrollConfiguration(
            behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              itemCount: champions.length + 1, // +1 for "All"
              separatorBuilder: (_, _) => const SizedBox(width: 6),
              itemBuilder: (_, i) {
                if (i == 0) {
                  // Tile "All"
                  return _FilterTile(
                    selected: selectedChampion == null,
                    onTap: () => onSelected(null),
                    child: Container(
                      width: double.infinity,
                      height: double.infinity,
                      color: kSurface2,
                      child: const Icon(Icons.texture, size: 32, color: kPrimaryLight),
                    ),
                  );
                }
                final champ = champions[i - 1];
                final iconUrl =
                    'https://ddragon.leagueoflegends.com/cdn/$version/img/champion/$champ.png';
                return _FilterTile(
                  selected: selectedChampion == champ,
                  onTap: () => onSelected(champ),
                  child: CachedNetworkImage(
                    imageUrl: iconUrl,
                    width: double.infinity,
                    height: double.infinity,
                    fit: BoxFit.cover,
                    placeholder: (_, _) => Container(color: kSurface2),
                    errorWidget: (_, _, _) => Center(
                      child: Text(
                        champ.substring(0, 1),
                        style: TextStyle(
                          fontSize: 14,
                          color: selectedChampion == champ ? kPrimaryLight : kMuted,
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _FilterTile extends StatelessWidget {
  const _FilterTile({
    required this.selected,
    required this.onTap,
    required this.child,
  });

  final bool         selected;
  final VoidCallback onTap;
  final Widget       child;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 48,
        height: 48,
        clipBehavior: Clip.antiAlias,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          color: selected ? kPrimary.withValues(alpha: 0.2) : kSurface2,
          border: Border.all(
            color: selected ? kPrimary : kBorderColor.withValues(alpha: 0.5),
            width: selected ? 2 : 1,
          ),
        ),
        child: Center(child: child),
      ),
    );
  }
}
