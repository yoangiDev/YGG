import 'package:cached_network_image/cached_network_image.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/player.dart';
import '../../models/snapshot_model.dart';
import '../../providers/ddragon_provider.dart';
import '../../providers/snapshot_provider.dart';
import '../rank_badge.dart';

class SnapshotDetailHeader extends ConsumerStatefulWidget {
  const SnapshotDetailHeader({
    super.key,
    required this.snapshot,
    required this.onUpdated,
    this.player,
  });

  final SnapshotModel snapshot;
  final void Function(SnapshotModel) onUpdated;
  final Player? player;

  @override
  ConsumerState<SnapshotDetailHeader> createState() => _SnapshotDetailHeaderState();
}

class _SnapshotDetailHeaderState extends ConsumerState<SnapshotDetailHeader> {
  bool _editingNotes = false;
  late final TextEditingController _notesCtrl;
  late final FocusNode _notesFocus;

  @override
  void initState() {
    super.initState();
    _notesCtrl = TextEditingController(text: widget.snapshot.notes);
    _notesFocus = FocusNode();
  }

  @override
  void dispose() {
    _notesCtrl.dispose();
    _notesFocus.dispose();
    super.dispose();
  }

  String _fmt(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  // Formato corto para móvil: DD/MM/YY  (evita overflow en Row 2)
  String _fmtShort(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year.toString().substring(2)}';

  void _showNotesModal() {
    _notesCtrl.text = widget.snapshot.notes;
    showDialog<void>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.55),
      builder: (dialogCtx) => Dialog(
        backgroundColor: kSurfaceColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: kPrimary.withValues(alpha: 0.25)),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'NOTES',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: kMuted, letterSpacing: 1.5),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _notesCtrl,
                autofocus: true,
                maxLines: 4,
                style: const TextStyle(fontSize: 13, color: kForeground),
                decoration: const InputDecoration(
                  hintText: 'Analyst notes…',
                  isDense: true,
                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        _notesCtrl.text = widget.snapshot.notes;
                        Navigator.of(dialogCtx).pop();
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: kMuted,
                        side: BorderSide(color: kMuted.withValues(alpha: 0.3)),
                      ),
                      child: const Text('Cancel'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        final notes = _notesCtrl.text.trim();
                        Navigator.of(dialogCtx).pop();
                        _saveNotes(notes);
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: kStatGreen.withValues(alpha: 0.15),
                        foregroundColor: kStatGreen,
                        shadowColor: Colors.transparent,
                        side: BorderSide(color: kStatGreen.withValues(alpha: 0.4)),
                        elevation: 0,
                      ),
                      child: const Text('Save'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _saveNotes(String notes) async {
    try {
      final repo = ref.read(snapshotRepositoryProvider);
      await repo.updateNotes(widget.snapshot.id, notes);
      // Actualiza estado local (para que el header muestre las notas sin recargar)
      widget.onUpdated(SnapshotModel(
        id:          widget.snapshot.id,
        playerId:    widget.snapshot.playerId,
        dateFrom:    widget.snapshot.dateFrom,
        dateTo:      widget.snapshot.dateTo,
        description: widget.snapshot.description,
        notes:       notes,
        matchCount:  widget.snapshot.matchCount,
      ));
      // Invalida la caché para que al volver a entrar las notas no desaparezcan
      ref.invalidate(snapshotsProvider(widget.snapshot.playerId));
    } on DioException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(e.message ?? 'Error saving notes.', style: const TextStyle(color: Colors.white)),
          backgroundColor: const Color(0xFF5A1A1A),
          behavior: SnackBarBehavior.floating,
        ));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final s       = widget.snapshot;
    final p       = widget.player;
    final version = ref.watch(ddragonVersionProvider).valueOrNull;
    final narrow  = MediaQuery.of(context).size.shortestSide < 600;

    if (narrow) {
      // Avatar (mismo tamaño que player detail)
      final avatarWidget = Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: kPrimary.withValues(alpha: 0.4), width: 2),
          boxShadow: [BoxShadow(color: kPrimary.withValues(alpha: 0.2), blurRadius: 14)],
          color: kSurface2,
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: p != null && version != null && p.profileIconId > 0
              ? CachedNetworkImage(
                  imageUrl: p.profileIconUrl(version),
                  fit: BoxFit.cover,
                  placeholder: (ctx, url) => const Center(
                    child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight),
                  ),
                  errorWidget: (ctx, url, err) => const Icon(Icons.person, color: kMuted, size: 26),
                )
              : const Icon(Icons.person, color: kMuted, size: 26),
        ),
      );

      return Container(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 10),
        decoration: BoxDecoration(
          color: kSurfaceColor,
          border: Border(bottom: BorderSide(color: kBorderColor.withValues(alpha: 0.5))),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [

            // ── Row 1: avatar | nombre + riotId + región | descripción del snapshot ──
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                avatarWidget,
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        p != null
                            ? (p.nickname.isNotEmpty ? p.nickname : p.gameName)
                            : 'Snapshot',
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: kForeground),
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (p != null) ...[
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            Flexible(
                              child: Text(
                                p.riotId,
                                style: const TextStyle(fontSize: 10, color: kMuted),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 5),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                              decoration: BoxDecoration(
                                color: kPrimary.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(p.region, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: kPrimaryLight)),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                // Descripción del snapshot (donde estaba UPDATE)
                Container(
                  constraints: const BoxConstraints(maxWidth: 110),
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  decoration: BoxDecoration(
                    color: kPrimary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: kPrimary.withValues(alpha: 0.25)),
                  ),
                  child: Text(
                    s.description.isNotEmpty ? s.description : 'Snapshot',
                    style: const TextStyle(fontSize: 10, color: kPrimaryLight, fontWeight: FontWeight.w600, letterSpacing: 0.2),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 10),

            // ── Row 2: RankBadge | Spacer | fechas | divider | partidas ──────────
            // Cotas explícitas para evitar overflow: badge ≤140 + fechas ≤120 + divider 17 + games 44 = ≤321 < 336
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                if (p != null) ...[
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 150),
                    child: RankBadge(tier: p.tier, division: p.rank, lp: p.lp, region: p.region),
                  ),
                  const Spacer(),
                ],
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 120),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('PERIOD', style: TextStyle(fontSize: 9, color: kMuted, letterSpacing: 1.0)),
                      const SizedBox(height: 3),
                      Text(
                        '${_fmtShort(s.dateFrom)} → ${_fmtShort(s.dateTo)}',
                        style: const TextStyle(fontSize: 10, color: kForeground, fontWeight: FontWeight.w500),
                        overflow: TextOverflow.ellipsis,
                        maxLines: 1,
                      ),
                    ],
                  ),
                ),
                Container(
                  width: 1,
                  height: 28,
                  margin: const EdgeInsets.symmetric(horizontal: 8),
                  color: kPrimary.withValues(alpha: 0.25),
                ),
                SizedBox(
                  width: 44,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('GAMES', style: TextStyle(fontSize: 9, color: kMuted, letterSpacing: 1.0)),
                      const SizedBox(height: 3),
                      Text(
                        '${s.matchCount}',
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: kForeground),
                      ),
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(height: 8),

            // ── Row 3: notas (tap → modal) ────────────────────────────────────────
            GestureDetector(
              onTap: _showNotesModal,
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      s.notes.isNotEmpty ? s.notes : 'Tap to add notes…',
                      style: TextStyle(
                        fontSize: 11,
                        fontStyle: FontStyle.italic,
                        color: s.notes.isNotEmpty ? kMuted : kMuted.withValues(alpha: 0.4),
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Icon(Icons.edit_outlined, size: 12, color: kMuted.withValues(alpha: 0.45)),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        border: Border(bottom: BorderSide(color: kBorderColor.withValues(alpha: 0.5))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [

          // Back
          IconButton(
            icon: const Icon(Icons.arrow_back_ios, size: 18, color: kMuted),
            onPressed: () => Navigator.of(context).pop(),
            tooltip: 'Back',
          ),
          const SizedBox(width: 12),

          // ── Sección jugador ────────────────────────────────────────────
          if (p != null) ...[
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: kPrimary.withValues(alpha: 0.4), width: 2),
                boxShadow: [BoxShadow(color: kPrimary.withValues(alpha: 0.2), blurRadius: 14)],
                color: kSurface2,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: version != null && p.profileIconId > 0
                    ? CachedNetworkImage(
                        imageUrl: p.profileIconUrl(version),
                        fit: BoxFit.cover,
                        placeholder: (ctx, url) => const Center(
                          child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight),
                        ),
                        errorWidget: (ctx, url, err) => const Icon(Icons.person, color: kMuted, size: 32),
                      )
                    : const Icon(Icons.person, color: kMuted, size: 32),
              ),
            ),
            const SizedBox(width: 20),

            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  p.nickname.isNotEmpty ? p.nickname : p.gameName,
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: kForeground),
                ),
                const SizedBox(height: 3),
                Row(
                  children: [
                    Text(p.riotId, style: const TextStyle(fontSize: 12, color: kMuted)),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: kPrimary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(p.region,
                          style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: kPrimaryLight)),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(width: 40),

            RankBadge(tier: p.tier, division: p.rank, lp: p.lp, region: p.region),
            const SizedBox(width: 20),

            Container(
              width: 1,
              height: 40,
              color: kBorderColor.withValues(alpha: 0.5),
            ),
            const SizedBox(width: 20),
          ],

          // ── Sección snapshot ───────────────────────────────────────────
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 280),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  s.description.isNotEmpty ? s.description : 'Snapshot',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: kForeground,
                  ),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
                const SizedBox(height: 3),
                Row(
                  children: [
                    const Icon(Icons.calendar_today_outlined, size: 11, color: kMuted),
                    const SizedBox(width: 5),
                    Text(
                      '${_fmt(s.dateFrom)}  →  ${_fmt(s.dateTo)}',
                      style: const TextStyle(fontSize: 12, color: kMuted),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 40),

          // ── Notas ──────────────────────────────────────────────────────
          Expanded(
            child: _editingNotes
                ? TapRegion(
                    onTapOutside: (_) {
                      _saveNotes(_notesCtrl.text.trim());
                      setState(() => _editingNotes = false);
                    },
                    child: Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _notesCtrl,
                            focusNode: _notesFocus,
                            autofocus: true,
                            maxLines: 2,
                            style: const TextStyle(fontSize: 12, color: kForeground),
                            decoration: const InputDecoration(
                              hintText: 'Analyst notes…',
                              isDense: true,
                              contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        IconButton(
                          icon: const Icon(Icons.check, size: 16, color: kStatGreen),
                          onPressed: () {
                            _saveNotes(_notesCtrl.text.trim());
                            setState(() => _editingNotes = false);
                          },
                          constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                          padding: EdgeInsets.zero,
                        ),
                        IconButton(
                          icon: const Icon(Icons.close, size: 16, color: kMuted),
                          onPressed: () {
                            _notesCtrl.text = widget.snapshot.notes;
                            setState(() => _editingNotes = false);
                          },
                          constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                          padding: EdgeInsets.zero,
                        ),
                      ],
                    ),
                  )
                : MouseRegion(
                    cursor: SystemMouseCursors.click,
                    child: GestureDetector(
                      onTap: () => setState(() => _editingNotes = true),
                      child: Text(
                        s.notes.isNotEmpty ? s.notes : 'No notes — click to add',
                        style: TextStyle(
                          fontSize: 12,
                          fontStyle: FontStyle.italic,
                          color: s.notes.isNotEmpty
                              ? kMuted
                              : kMuted.withValues(alpha: 0.4),
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}
