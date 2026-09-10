import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/shimmer.dart';
import '../models/match_model.dart';
import '../providers/ddragon_provider.dart';
import '../providers/match_provider.dart';
import 'match_icons.dart';

const _kColHeader = TextStyle(
  fontSize: 9,
  letterSpacing: 1.6,
  color: Color(0xFF4A4560),
  fontWeight: FontWeight.w600,
);

class MatchHistoryPanel extends ConsumerWidget {
  const MatchHistoryPanel({super.key, required this.playerId});
  final int playerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final matchesAsync = ref.watch(playerMatchesProvider(playerId));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: kBorderColor.withValues(alpha: 0.4))),
          ),
          child: Row(
            children: [
              const Text('RECENT MATCHES', style: _kColHeader),
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
        ),
        Expanded(
          child: matchesAsync.when(
            loading: () => const _MatchHistorySkeleton(),
            error: (e, _) => Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    e is DioException ? e.userMessage : 'Failed to load matches.',
                    style: const TextStyle(color: kMuted, fontSize: 12),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  TextButton.icon(
                    onPressed: () => ref.invalidate(playerMatchesProvider(playerId)),
                    icon: const Icon(Icons.refresh, size: 14, color: kPrimaryLight),
                    label: const Text('Retry', style: TextStyle(fontSize: 12, color: kPrimaryLight)),
                  ),
                ],
              ),
            ),
            data: (matches) => matches.isEmpty
                ? const Center(child: Text('No recent matches', style: TextStyle(color: kMuted, fontSize: 13)))
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    itemCount: matches.length,
                    itemBuilder: (_, i) => MatchRow(match: matches[i]),
                  ),
          ),
        ),
      ],
    );
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _MatchHistorySkeleton extends StatelessWidget {
  const _MatchHistorySkeleton();

  static const _spellRune = Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      Row(mainAxisSize: MainAxisSize.min, children: [
        ShimmerBox(width: 26, height: 26, radius: 3),
        SizedBox(width: 2),
        ShimmerBox(width: 26, height: 26, radius: 13),
      ]),
      SizedBox(height: 2),
      Row(mainAxisSize: MainAxisSize.min, children: [
        ShimmerBox(width: 26, height: 26, radius: 3),
        SizedBox(width: 2),
        ShimmerBox(width: 26, height: 26, radius: 13),
      ]),
    ],
  );

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Shimmer(
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 6),
        itemCount: 8,
        itemBuilder: (_, _) {
          if (narrow) {
            return Container(
              margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
              decoration: BoxDecoration(
                color: kSurface2.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(6),
                border: Border(left: BorderSide(color: kPrimary.withValues(alpha: 0.25), width: 3)),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Fila 1: champion | spells | CS/KP/VIS | K/D/A centrado | tiempo
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      const ShimmerBox(width: 54, height: 54, radius: 6),
                      const SizedBox(width: 6),
                      _spellRune,
                      const SizedBox(width: 8),
                      // CS/KP/VIS
                      SizedBox(
                        width: 52,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          mainAxisSize: MainAxisSize.min,
                          children: const [
                            ShimmerBox(height: 9),
                            SizedBox(height: 3),
                            ShimmerBox(height: 9),
                            SizedBox(height: 3),
                            ShimmerBox(height: 9),
                          ],
                        ),
                      ),
                      // K/D/A + KDA centrados
                      Expanded(
                        child: Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: const [
                              ShimmerBox(width: 55, height: 14, radius: 2),
                              SizedBox(height: 3),
                              ShimmerBox(width: 38, height: 9, radius: 2),
                            ],
                          ),
                        ),
                      ),
                      // Tiempo
                      SizedBox(
                        width: 64,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          mainAxisSize: MainAxisSize.min,
                          children: const [
                            ShimmerBox(height: 9),
                            SizedBox(height: 3),
                            ShimmerBox(height: 9),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 7),
                  // Fila 2: items + Victory/Defeat
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Expanded(
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: List.generate(8, (_) => const Padding(
                              padding: EdgeInsets.only(right: 3),
                              child: ShimmerBox(width: 34, height: 34, radius: 4),
                            )),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      const ShimmerBox(width: 44, height: 11, radius: 2),
                    ],
                  ),
                ],
              ),
            );
          }

          // Desktop
          return Container(
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: kSurface2.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(6),
              border: Border(left: BorderSide(color: kPrimary.withValues(alpha: 0.25), width: 3)),
            ),
            child: Row(
              children: [
                const ShimmerBox(width: 54, height: 54, radius: 6),
                const SizedBox(width: 8),
                _spellRune,
                const SizedBox(width: 16),
                Expanded(child: FittedBox(fit: BoxFit.scaleDown, child: const ShimmerBox(width: 44, height: 32))),
                const SizedBox(width: 16),
                Expanded(child: FittedBox(fit: BoxFit.scaleDown, child: const ShimmerBox(width: 80, height: 22))),
                const SizedBox(width: 16),
                Expanded(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.center,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: const [
                        ShimmerBox(width: 60, height: 12),
                        SizedBox(height: 4),
                        ShimmerBox(width: 50, height: 12),
                        SizedBox(height: 4),
                        ShimmerBox(width: 40, height: 12),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  flex: 3,
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.center,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: List.generate(7, (_) => const Padding(
                        padding: EdgeInsets.only(right: 3),
                        child: ShimmerBox(width: 34, height: 34, radius: 4),
                      )),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisSize: MainAxisSize.min,
                  children: const [
                    ShimmerBox(width: 52, height: 12),
                    SizedBox(height: 4),
                    ShimmerBox(width: 64, height: 11),
                    SizedBox(height: 4),
                    ShimmerBox(width: 72, height: 11),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

// ── Fila de partida ───────────────────────────────────────────────────────────

class MatchRow extends ConsumerWidget {
  const MatchRow({super.key, required this.match});
  final MatchModel match;

  Color _kdaColor(double kda) {
    if (kda >= 5) return kStatGold;
    if (kda >= 4) return kStatBlue;
    if (kda >= 3) return kStatGreen;
    return kStatGray;
  }

  String _duration(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '${m}m ${s.toString().padLeft(2, '0')}s';
  }

  String _timeAgo(DateTime t) {
    final diff = DateTime.now().difference(t);
    if (diff.inDays >= 30) {
      final months = (diff.inDays / 30).round();
      return '$months ${months == 1 ? "month" : "months"} ago';
    }
    if (diff.inDays >= 1) {
      final days = (diff.inHours / 24).round();
      return '$days ${days == 1 ? "day" : "days"} ago';
    }
    if (diff.inMinutes >= 60) {
      final hours = (diff.inMinutes / 60).round();
      return '$hours ${hours == 1 ? "hour" : "hours"} ago';
    }
    return '${diff.inMinutes}m ago';
  }

  Widget _buildItemsRow(Map<int, dynamic> itemData, String? version) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      for (final id in match.buildItems)
        Padding(
          padding: const EdgeInsets.only(right: 3),
          child: MatchItemIcon(itemId: id, version: version, data: itemData[id]),
        ),
      Padding(
        padding: const EdgeInsets.only(right: 3),
        child: MatchQuestItemIcon(
          itemId: match.questDisplayItemId,
          version: version,
          data: match.questDisplayItemId > 0 ? itemData[match.questDisplayItemId] : null,
          completed: match.questCompletionTime != null,
          completionTime: match.questCompletionTime,
          enemyCompletionTime: match.enemyQuestCompletionTime,
          diff: match.questCompletionTimeDiff,
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(right: 3),
        child: MatchItemIcon(itemId: match.trinket, version: version, isTrinket: true, data: itemData[match.trinket]),
      ),
    ],
  );

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final version   = ref.watch(ddragonVersionProvider).valueOrNull;
    final spellMap  = ref.watch(spellIconsProvider).valueOrNull ?? {};
    final spellData = ref.watch(spellDataProvider).valueOrNull ?? {};
    final itemData  = ref.watch(itemDataProvider).valueOrNull ?? {};
    final runeMap   = ref.watch(runeIconsProvider).valueOrNull ?? {};
    final kda       = match.kdaValue;
    final winColor  = match.win ? kStatGreen : kStatRed;
    final bgColor   = match.win
        ? kStatGreen.withValues(alpha: 0.06)
        : kStatRed.withValues(alpha: 0.06);

    final spell1Url = spellMap[match.summoner1Id];
    final spell2Url = spellMap[match.summoner2Id];
    final narrow    = MediaQuery.of(context).size.width < 600;

    final spellRuneWidget = Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(mainAxisSize: MainAxisSize.min, children: [
          MatchSpellIcon(url: spell1Url, data: spellData[match.summoner1Id]),
          const SizedBox(width: 2),
          MatchRuneIcon(runeId: match.primaryRune, runes: runeMap),
        ]),
        const SizedBox(height: 2),
        Row(mainAxisSize: MainAxisSize.min, children: [
          MatchSpellIcon(url: spell2Url, data: spellData[match.summoner2Id]),
          const SizedBox(width: 2),
          MatchRuneIcon(runeId: match.secondaryTree, runes: runeMap),
        ]),
      ],
    );

    if (narrow) {
      // Layout móvil: 2 filas. El color ya indica victoria/derrota → sin texto redundante
      return Container(
        margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(6),
          border: Border(left: BorderSide(color: winColor, width: 3)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Fila 1: campeón(54) | spells + CS/KP/VIS | K/D/A+KDA centrado | tiempo
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                MatchChampionIcon(champion: match.champion, version: version, size: 54),
                const SizedBox(width: 6),
                spellRuneWidget,
                const SizedBox(width: 8),
                // CS/KP/VIS junto a los spells, centrados (ancho fijo para no robar espacio al Expanded)
                SizedBox(
                  width: 52,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text('${match.csPerMin.toStringAsFixed(1)} CS/m', style: const TextStyle(fontSize: 9, color: kMuted), overflow: TextOverflow.ellipsis, maxLines: 1),
                      const SizedBox(height: 3),
                      Text('${match.killParticipation.toStringAsFixed(0)}% KP',  style: const TextStyle(fontSize: 9, color: kMuted), overflow: TextOverflow.ellipsis, maxLines: 1),
                      const SizedBox(height: 3),
                      Text('${match.vision} VIS',                                 style: const TextStyle(fontSize: 9, color: kMuted), overflow: TextOverflow.ellipsis, maxLines: 1),
                    ],
                  ),
                ),
                // K/D/A + KDA centrados en el espacio restante, escalan si hace falta
                Expanded(
                  child: Center(
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.baseline,
                            textBaseline: TextBaseline.alphabetic,
                            children: [
                              Text('${match.kills}',   style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: kForeground)),
                              const Text('/',          style: TextStyle(fontSize: 12, color: kMuted)),
                              Text('${match.deaths}',  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: kStatRed)),
                              const Text('/',          style: TextStyle(fontSize: 12, color: kMuted)),
                              Text('${match.assists}', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: kForeground)),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${kda.toStringAsFixed(1)} KDA',
                            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: _kdaColor(kda)),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                // Duración + tiempo (ancho fijo: evita que "12 months ago" expanda el Row)
                SizedBox(
                  width: 64,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_duration(match.duration), style: const TextStyle(fontSize: 10, color: kMuted), overflow: TextOverflow.ellipsis, maxLines: 1),
                      Text(_timeAgo(match.creationTime), style: const TextStyle(fontSize: 9, color: kMuted), overflow: TextOverflow.ellipsis, maxLines: 1),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 7),
            // Fila 2: items + Victory/Defeat a la derecha
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: _buildItemsRow(itemData, version),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  match.win ? 'Victory' : 'Defeat',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: winColor),
                ),
              ],
            ),
          ],
        ),
      );
    }

    // Layout escritorio (sin cambios)
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(6),
        border: Border(left: BorderSide(color: winColor, width: 3)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          MatchChampionIcon(champion: match.champion, version: version, size: 54),
          const SizedBox(width: 8),
          spellRuneWidget,
          const SizedBox(width: 16),
          Expanded(
            flex: 1,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.center,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    kda.toStringAsFixed(2),
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: _kdaColor(kda)),
                  ),
                  Text(
                    'KDA',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: _kdaColor(kda).withValues(alpha: 0.7)),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            flex: 1,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.center,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Text('${match.kills}',   style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: kForeground)),
                  const Text(' / ',        style: TextStyle(fontSize: 14, color: kMuted)),
                  Text('${match.deaths}',  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: kStatRed)),
                  const Text(' / ',        style: TextStyle(fontSize: 14, color: kMuted)),
                  Text('${match.assists}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: kForeground)),
                ],
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            flex: 1,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.center,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('${match.csPerMin.toStringAsFixed(1)} CS/m',          style: const TextStyle(fontSize: 12, color: kMuted)),
                  Text('${match.killParticipation.toStringAsFixed(0)}% KP',  style: const TextStyle(fontSize: 12, color: kMuted)),
                  Text('${match.vision} VIS',                                 style: const TextStyle(fontSize: 12, color: kMuted)),
                ],
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            flex: 3,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.center,
              child: _buildItemsRow(itemData, version),
            ),
          ),
          const SizedBox(width: 16),
          SizedBox(
            width: 90,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  match.win ? 'Victory' : 'Defeat',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: winColor),
                ),
                Text(_duration(match.duration), style: const TextStyle(fontSize: 11, color: kMuted)),
                Text(_timeAgo(match.creationTime), style: const TextStyle(fontSize: 11, color: kMuted)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
