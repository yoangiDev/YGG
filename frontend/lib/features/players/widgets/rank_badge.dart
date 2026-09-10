import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/rank_cutoffs_model.dart';
import '../providers/rank_cutoffs_provider.dart';

class _RankStyle {
  const _RankStyle({required this.barColor});
  final Color barColor;
}

const _rankStyles = <String, _RankStyle>{
  'IRON':        _RankStyle(barColor: Color(0xFF555566)),
  'BRONZE':      _RankStyle(barColor: Color(0xFFC0693A)),
  'SILVER':      _RankStyle(barColor: Color(0xFF7A8FA8)),
  'GOLD':        _RankStyle(barColor: Color(0xFFC8960F)),
  'PLATINUM':    _RankStyle(barColor: Color(0xFF00B09E)),
  'EMERALD':     _RankStyle(barColor: Color(0xFF2ECC6E)),
  'DIAMOND':     _RankStyle(barColor: Color(0xFF5090F0)),
  'MASTER':      _RankStyle(barColor: Color(0xFFA050D0)),
  'GRANDMASTER': _RankStyle(barColor: Color(0xFFE04030)),
  'CHALLENGER':  _RankStyle(barColor: Color(0xFFF0D020)),
};

const _tierAssets = <String, String>{
  'IRON':        'assets/rank_badges/iron_badge.png',
  'BRONZE':      'assets/rank_badges/bronze_badge.png',
  'SILVER':      'assets/rank_badges/silver_badge.png',
  'GOLD':        'assets/rank_badges/gold_badge.png',
  'PLATINUM':    'assets/rank_badges/platinum_badge.png',
  'EMERALD':     'assets/rank_badges/emerald_badge.png',
  'DIAMOND':     'assets/rank_badges/diamond_badge.png',
  'MASTER':      'assets/rank_badges/master_badge.png',
  'GRANDMASTER': 'assets/rank_badges/grandmaster_badge.png',
  'CHALLENGER':  'assets/rank_badges/challenger_badge.png',
};

class RankBadge extends ConsumerWidget {
  const RankBadge({
    super.key,
    required this.tier,
    required this.division,
    required this.lp,
    required this.region,
    this.lpOnly = false,
  });

  final String tier;
  final String division;
  final int    lp;
  final String region;
  final bool   lpOnly;

  ({double factor, int? targetLp, String lpLabel}) _progress(
    String tierUpper,
    int lpValue,
    RankCutoffs? cutoffs,
  ) {
    if (tierUpper == 'MASTER') {
      final target = cutoffs?.grandmasterCutoffLp ?? 1100;
      return (
        factor:   (lpValue / target).clamp(0.0, 1.0),
        targetLp: cutoffs?.grandmasterCutoffLp,
        lpLabel:  cutoffs != null ? '$lpValue / $target LP' : '$lpValue LP',
      );
    }
    if (tierUpper == 'GRANDMASTER') {
      final target = cutoffs?.challengerCutoffLp ?? 1600;
      return (
        factor:   (lpValue / target).clamp(0.0, 1.0),
        targetLp: cutoffs?.challengerCutoffLp,
        lpLabel:  cutoffs != null ? '$lpValue / $target LP' : '$lpValue LP',
      );
    }
    if (tierUpper == 'CHALLENGER' && cutoffs != null) {
      final target = cutoffs.challengerCutoffLp;
      return (
        factor:   (lpValue / target).clamp(0.0, 1.0),
        targetLp: target,
        lpLabel:  '$lpValue LP',
      );
    }
    return (
      factor:   (lpValue / 100).clamp(0.0, 1.0),
      targetLp: null,
      lpLabel:  '$lpValue LP',
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cutoffsMap = ref.watch(rankCutoffsProvider);
    final cutoffs    = rankCutoffsForRegion(cutoffsMap, region);

    final style = _rankStyles[tier.toUpperCase()];
    final showDivision = !['MASTER', 'GRANDMASTER', 'CHALLENGER'].contains(tier.toUpperCase());

    final isUnranked = style == null || tier.isEmpty;
    final assetPath  = isUnranked
        ? 'assets/rank_badges/unranked_badge.png'
        : _tierAssets[tier.toUpperCase()]!;
    final barColor   = style?.barColor ?? const Color(0xFF3A3550);
    final labelText  = isUnranked
        ? 'UNRANKED'
        : (showDivision ? '${tier.toUpperCase()} $division' : tier.toUpperCase());
    final lpValue    = isUnranked ? 0 : lp;
    final tierUpper  = tier.toUpperCase();
    final progress   = _progress(tierUpper, lpValue, cutoffs);
    final lpLabel    = lpOnly ? '$lpValue LP' : progress.lpLabel;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 44,
          height: 44,
          child: Image.asset(assetPath, fit: BoxFit.contain),
        ),
        const SizedBox(width: 10),
        Flexible(
          fit: FlexFit.loose,
          child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              labelText,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: isUnranked
                    ? const Color(0xFF6B6578)
                    : const Color(0xFFE8E0F5),
              ),
              overflow: TextOverflow.ellipsis,
              maxLines: 1,
            ),
            const SizedBox(height: 4),
            Tooltip(
              message: progress.targetLp != null
                  ? 'Daily cutoff: ${progress.targetLp} LP'
                  : lpLabel,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 56,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(2),
                    ),
                    child: FractionallySizedBox(
                      alignment: Alignment.centerLeft,
                      widthFactor: progress.factor,
                      child: Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [barColor, barColor.withValues(alpha: 0.5)],
                          ),
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      lpLabel,
                      style: const TextStyle(fontSize: 10, color: Color(0xFF6B6578)),
                      overflow: TextOverflow.ellipsis,
                      maxLines: 1,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        ), // end Flexible
      ],
    );
  }
}
