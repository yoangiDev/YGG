import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../models/match_model.dart';
import '../utils/quest_item_icon.dart';
import 'match_icon_tooltip.dart';

class MatchChampionIcon extends StatelessWidget {
  const MatchChampionIcon({super.key, required this.champion, required this.version, this.size = 36});
  final String  champion;
  final String? version;
  final double  size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: kBorderColor.withValues(alpha: 0.6)),
        color: kSurface2,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(5),
        child: version != null
            ? CachedNetworkImage(
                imageUrl: 'https://ddragon.leagueoflegends.com/cdn/$version/img/champion/$champion.png',
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
                errorWidget: (ctx, url, err) => const Center(
                  child: Icon(Icons.sports_esports, color: kMuted, size: 16),
                ),
              )
            : const SizedBox.shrink(),
      ),
    );
  }
}

class MatchItemIcon extends StatelessWidget {
  const MatchItemIcon({super.key, required this.itemId, required this.version, this.isTrinket = false, this.data});
  final int     itemId;
  final String? version;
  final bool    isTrinket;
  final ({String name, String desc, int cost})? data;

  @override
  Widget build(BuildContext context) {
    const double size = 34;
    final radius = isTrinket ? 13.0 : 4.0;

    final icon = itemId == 0 || version == null
        ? Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              color: kSurface2.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(radius),
              border: Border.all(color: kBorderColor.withValues(alpha: 0.3)),
            ),
          )
        : Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(radius),
              border: Border.all(color: kBorderColor.withValues(alpha: 0.7)),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(radius - 1),
              child: CachedNetworkImage(
                imageUrl: 'https://ddragon.leagueoflegends.com/cdn/$version/img/item/$itemId.png',
                fit: BoxFit.cover,
                placeholder: (ctx, url) => Container(
                  color: kSurface2,
                  child: const Center(
                    child: SizedBox(
                      width: 12,
                      height: 12,
                      child: CircularProgressIndicator(strokeWidth: 1.0, color: kPrimaryLight),
                    ),
                  ),
                ),
                errorWidget: (ctx, url, err) => Container(
                  color: kSurface2,
                  child: const Center(child: Icon(Icons.remove, size: 10, color: kMuted)),
                ),
              ),
            ),
          );

    if (data == null || data!.name.isEmpty) return icon;
    return MatchIconTooltip(title: data!.name, description: data!.desc, cost: data!.cost, child: icon);
  }
}

class MatchSpellIcon extends StatelessWidget {
  const MatchSpellIcon({super.key, required this.url, this.data});
  final String? url;
  final ({String name, String desc, int cooldown})? data;

  @override
  Widget build(BuildContext context) {
    final icon = Container(
      width: 26,
      height: 26,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(3),
        border: Border.all(color: kBorderColor.withValues(alpha: 0.7)),
        color: kSurface2,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(2),
        child: url != null
            ? CachedNetworkImage(
                imageUrl: url!,
                fit: BoxFit.cover,
                placeholder: (ctx, url) => Container(
                  color: kSurface2,
                  child: const Center(
                    child: SizedBox(
                      width: 10,
                      height: 10,
                      child: CircularProgressIndicator(strokeWidth: 1.0, color: kPrimaryLight),
                    ),
                  ),
                ),
                errorWidget: (ctx, url, err) => const SizedBox.shrink(),
              )
            : const SizedBox.shrink(),
      ),
    );

    if (data == null || data!.name.isEmpty) return icon;
    return MatchIconTooltip(title: data!.name, description: data!.desc, cooldown: data!.cooldown, child: icon);
  }
}

class MatchRuneIcon extends StatelessWidget {
  const MatchRuneIcon({super.key, required this.runeId, required this.runes});
  final int    runeId;
  final Map<int, ({String name, String icon, String desc})> runes;

  @override
  Widget build(BuildContext context) {
    final rune = runeId > 0 ? runes[runeId] : null;
    final icon = Container(
      width: 26,
      height: 26,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: kSurface2,
        border: Border.all(color: kBorderColor.withValues(alpha: 0.5)),
      ),
      child: ClipOval(
        child: rune != null
            ? CachedNetworkImage(
                imageUrl: rune.icon,
                fit: BoxFit.cover,
                placeholder: (ctx, url) => Container(
                  color: kSurface2,
                  child: const Center(
                    child: SizedBox(
                      width: 10,
                      height: 10,
                      child: CircularProgressIndicator(strokeWidth: 1.0, color: kPrimaryLight),
                    ),
                  ),
                ),
                errorWidget: (ctx, url, err) => const SizedBox.shrink(),
              )
            : const SizedBox.shrink(),
      ),
    );

    if (rune == null || rune.name.isEmpty) return icon;
    return MatchIconTooltip(title: rune.name, description: rune.desc, child: icon);
  }
}

class MatchQuestItemIcon extends StatelessWidget {
  const MatchQuestItemIcon({
    super.key,
    required this.itemId,
    required this.version,
    this.data,
    this.completed = false,
    this.completionTime,
    this.enemyCompletionTime,
    this.diff,
  });

  final int itemId;
  final String? version;
  final ({String name, String desc, int cost})? data;
  final bool completed;
  final int? completionTime;
  final int? enemyCompletionTime;
  final int? diff;

  @override
  Widget build(BuildContext context) {
    const double size = 34;
    Color borderColor = kBorderColor.withValues(alpha: 0.5);
    if (completed && diff != null) {
      borderColor = diff! < 0 ? kStatGreen : diff! > 0 ? kStatRed : kPrimaryLight;
    } else if (completed) {
      borderColor = kPrimaryLight;
    }

    final imageUrl = questItemIconUrl(itemId, version);

    final icon = itemId == 0 || imageUrl == null
        ? Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              color: kSurface2.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: kBorderColor.withValues(alpha: 0.3)),
            ),
            child: itemId > 0
                ? Icon(Icons.flag_outlined, size: 16, color: kPrimaryLight.withValues(alpha: 0.7))
                : null,
          )
        : Opacity(
            opacity: completed ? 1.0 : 0.45,
            child: Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: borderColor, width: 1.5),
                boxShadow: completed
                    ? [BoxShadow(color: borderColor.withValues(alpha: 0.35), blurRadius: 4)]
                    : null,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(3),
                child: CachedNetworkImage(
                  imageUrl: imageUrl,
                  fit: BoxFit.cover,
                  placeholder: (ctx, url) => Container(
                    color: kSurface2,
                    child: const Center(
                      child: SizedBox(
                        width: 12,
                        height: 12,
                        child: CircularProgressIndicator(strokeWidth: 1.0, color: kPrimaryLight),
                      ),
                    ),
                  ),
                  errorWidget: (ctx, url, err) => Container(
                    color: kSurface2,
                    child: Center(
                      child: Icon(Icons.workspace_premium, size: 16, color: kPrimaryLight.withValues(alpha: 0.85)),
                    ),
                  ),
                ),
              ),
            ),
          );

    final lines = <String>['Role Quest reward'];
    if (completionTime != null) {
      lines.add('Completed: ${MatchModel.formatQuestTime(completionTime!)}');
    } else if (itemId > 0) {
      lines.add('Not completed');
    }
    if (enemyCompletionTime != null) {
      lines.add('Enemy: ${MatchModel.formatQuestTime(enemyCompletionTime!)}');
    }
    if (diff != null) {
      lines.add('Diff: ${MatchModel.formatQuestDiff(diff!)}');
    }

    final title = data?.name.isNotEmpty == true ? data!.name : 'Role Quest';
    final desc = data?.desc.isNotEmpty == true ? data!.desc : lines.join('\n');

    return MatchIconTooltip(
      title: title,
      description: desc,
      cost: data?.cost,
      child: icon,
    );
  }
}
