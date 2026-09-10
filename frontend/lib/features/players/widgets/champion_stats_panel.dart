import 'package:cached_network_image/cached_network_image.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/shimmer.dart';
import '../models/most_played_champion_model.dart';
import '../providers/match_provider.dart';

const _kColHeader = TextStyle(
  fontSize: 9,
  letterSpacing: 1.6,
  color: Color(0xFF4A4560),
  fontWeight: FontWeight.w600,
);

class ChampionStatsPanel extends ConsumerWidget {
  const ChampionStatsPanel({super.key, required this.playerId});
  final int playerId;

  Color _wrColor(double wr) {
    if (wr >= 55) return kStatGold;
    if (wr >= 50) return kStatBlue;
    if (wr >= 45) return kStatGreen;
    return kStatGray;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final championsAsync = ref.watch(mostPlayedProvider(playerId));

    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Text('MOST PLAYED CHAMPIONS', style: _kColHeader),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: kPrimary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'Last 20 games',
                  style: TextStyle(fontSize: 9, color: kPrimaryLight, letterSpacing: 0.5),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          championsAsync.when(
            loading: () => const _ChampionStatsSkeleton(),
            error: (e, _) => Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  e is DioException ? e.userMessage : 'Failed to load champions.',
                  style: const TextStyle(color: kMuted, fontSize: 11),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: () => ref.invalidate(mostPlayedProvider(playerId)),
                  icon: const Icon(Icons.refresh, size: 14, color: kPrimaryLight),
                  label: const Text('Retry', style: TextStyle(fontSize: 12, color: kPrimaryLight)),
                ),
              ],
            ),
            data: (champions) => champions.isEmpty
                ? const Text('No data', style: TextStyle(color: kMuted, fontSize: 12))
                : Column(
                    children: champions
                        .map((c) => Padding(
                              padding: const EdgeInsets.only(bottom: 10),
                              child: _ChampionRow(champion: c, wrColor: _wrColor(c.winRate)),
                            ))
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _ChampionStatsSkeleton extends StatelessWidget {
  const _ChampionStatsSkeleton();

  @override
  Widget build(BuildContext context) {
    return Shimmer(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(3, (_) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Row(
            children: const [
              ShimmerBox(width: 38, height: 38, radius: 19),
              SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    ShimmerBox(width: 100, height: 12),
                    SizedBox(height: 4),
                    ShimmerBox(width: 60, height: 10),
                  ],
                ),
              ),
              SizedBox(width: 8),
              ShimmerBox(width: 36, height: 34, radius: 4),
            ],
          ),
        )),
      ),
    );
  }
}

class _ChampionRow extends StatelessWidget {
  const _ChampionRow({required this.champion, required this.wrColor});
  final MostPlayedChampion champion;
  final Color              wrColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: kBorderColor.withValues(alpha: 0.7)),
            color: kSurface2,
          ),
          child: ClipOval(
            child: CachedNetworkImage(
              imageUrl: champion.iconUrl,
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
              errorWidget: (ctx, url, err) => const Icon(Icons.person, color: kMuted, size: 18),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                champion.championName,
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kForeground),
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 3),
              // Barra de winrate
              ClipRRect(
                borderRadius: BorderRadius.circular(99),
                child: LinearProgressIndicator(
                  value: (champion.winRate / 100).clamp(0.0, 1.0),
                  backgroundColor: kSurface2,
                  color: wrColor,
                  minHeight: 3,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '${champion.gamesPlayed} games',
                style: const TextStyle(fontSize: 10, color: kMuted),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '${champion.winRate.toStringAsFixed(0)}%',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: wrColor),
            ),
            Text(
              'WR',
              style: TextStyle(fontSize: 9, color: wrColor.withValues(alpha: 0.6), letterSpacing: 0.8),
            ),
          ],
        ),
      ],
    );
  }
}
