import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/shimmer.dart';
import '../../providers/ddragon_provider.dart';
import '../../providers/match_provider.dart';

class ChampionFilterColumn extends ConsumerWidget {
  const ChampionFilterColumn({
    super.key,
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

    return matchesAsync.when(
      loading: () => const _ChampionColumnSkeleton(),
      error:   (e, _) => const SizedBox.shrink(),
      data: (matches) {
        final champions = matches
            .map((m) => m.champion)
            .toSet()
            .toList()
          ..sort();

        final version = versionAsync.valueOrNull ?? '16.10.1';

        return ScrollConfiguration(
          behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
          child: ListView(
            padding: const EdgeInsets.symmetric(vertical: 16),
            children: [
              Center(
                child: Tooltip(
                  message: 'All champions',
                  child: ChampTile(
                    selected: selectedChampion == null,
                    onTap: () => onSelected(null),
                    child: const Icon(Icons.texture, size: 40, color: kPrimaryLight),
                  ),
                ),
              ),
              ...champions.map<Widget>((String champ) {
                final iconUrl = 'https://ddragon.leagueoflegends.com/cdn/$version/img/champion/$champ.png';
                final isSelected = selectedChampion == champ;
                return Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Center(
                    child: Tooltip(
                      message: champ,
                      child: ChampTile(
                        selected: isSelected,
                        onTap: () => onSelected(champ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: CachedNetworkImage(
                            imageUrl: iconUrl,
                            width: 36,
                            height: 36,
                            fit: BoxFit.cover,
                            placeholder: (ctx, url) => Container(
                              color: kSurface2,
                              child: const Center(
                                child: SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight),
                                ),
                              ),
                            ),
                            errorWidget: (ctx, url, err) => Text(
                              champ.substring(0, 1),
                              style: TextStyle(fontSize: 12, color: isSelected ? kPrimaryLight : kMuted),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              }),
            ],
          ),
        );
      },
    );
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _ChampionColumnSkeleton extends StatelessWidget {
  const _ChampionColumnSkeleton();

  @override
  Widget build(BuildContext context) {
    return Shimmer(
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 14),
        itemCount: 8,
        separatorBuilder: (_, _) => const SizedBox(height: 10),
        itemBuilder: (_, _) => const ShimmerBox(width: 44, height: 44, radius: 8),
      ),
    );
  }
}

class ChampTile extends StatelessWidget {
  const ChampTile({super.key, required this.selected, required this.onTap, required this.child});
  final bool         selected;
  final VoidCallback onTap;
  final Widget       child;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
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
