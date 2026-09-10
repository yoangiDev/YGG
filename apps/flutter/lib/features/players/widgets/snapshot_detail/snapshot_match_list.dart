import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../providers/match_provider.dart';
import '../match_history_panel.dart';

class SnapshotMatchList extends ConsumerWidget {
  const SnapshotMatchList({
    super.key,
    required this.snapshotId,
    this.champion,
  });

  final int     snapshotId;
  final String? champion;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final matchesAsync = ref.watch(snapshotMatchesProvider(snapshotId));

    return matchesAsync.when(
      loading: () => const Center(
        child: CircularProgressIndicator(color: kPrimaryLight, strokeWidth: 2),
      ),
      error: (err, st) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Failed to load matches.', style: TextStyle(color: kMuted, fontSize: 12)),
            const SizedBox(height: 12),
            TextButton.icon(
              onPressed: () => ref.invalidate(snapshotMatchesProvider(snapshotId)),
              icon: const Icon(Icons.refresh, size: 14, color: kPrimaryLight),
              label: const Text('Retry', style: TextStyle(fontSize: 12, color: kPrimaryLight)),
            ),
          ],
        ),
      ),
      data: (all) {
        final matches = (champion == null
            ? all
            : all.where((m) => m.champion == champion).toList())
          ..sort((a, b) => b.creationTime.compareTo(a.creationTime));

        if (matches.isEmpty) {
          return const Center(
            child: Text('No matches', style: TextStyle(color: kMuted, fontSize: 13)),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.symmetric(vertical: 6),
          itemCount: matches.length,
          itemBuilder: (_, i) => MatchRow(match: matches[i]),
        );
      },
    );
  }
}
