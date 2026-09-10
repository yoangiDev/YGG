import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../features/players/models/player.dart';
import '../features/players/providers/ddragon_provider.dart';
import '../features/players/providers/match_provider.dart';
import '../features/players/providers/players_provider.dart';
import '../features/players/providers/snapshot_provider.dart';
import '../features/players/widgets/champion_stats_panel.dart';
import '../features/players/widgets/hextech_header.dart';
import '../features/players/widgets/match_history_panel.dart';
import '../features/players/widgets/rank_badge.dart';
import '../features/players/widgets/role_chip.dart';
import '../features/players/widgets/snapshot_panel.dart';

class PlayerDetailScreen extends ConsumerStatefulWidget {
  const PlayerDetailScreen({super.key, required this.player});
  final Player player;

  @override
  ConsumerState<PlayerDetailScreen> createState() => _PlayerDetailScreenState();
}

class _PlayerDetailScreenState extends ConsumerState<PlayerDetailScreen> {
  late Player _player;
  bool _autoRefreshing = false;

  @override
  void initState() {
    super.initState();
    _player = widget.player;
    _checkAutoRefresh();
  }

  // ── Auto-refresh al abrir el perfil ───────────────────────────────────────
  Future<void> _checkAutoRefresh() async {
    final needed = await shouldAutoRefresh(_player.id);
    if (!needed || !mounted) return;

    setState(() => _autoRefreshing = true);
    final err = await ref.read(playersProvider.notifier).refreshPlayer(_player.id);

    if (!mounted) return;
    setState(() => _autoRefreshing = false);

    if (err == null) {
      final updated = ref.read(playersProvider).valueOrNull
          ?.firstWhere((p) => p.id == _player.id, orElse: () => _player);
      if (updated != null && mounted) {
        setState(() => _player = updated);
      }
    }
  }

  Future<void> _saveNotes(String notes) async {
    final data = PlayerUpdateData(
      gameName: _player.gameName,
      tagLine:  _player.tagLine,
      role:     _player.role,
      nickname: _player.nickname,
      notes:    notes,
    );
    final err = await ref.read(playersProvider.notifier).updatePlayer(_player.id, data);
    if (err != null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(err, style: const TextStyle(color: Colors.white)),
          backgroundColor: const Color(0xFF5A1A1A),
        ),
      );
    } else {
      setState(() => _player = _player.copyWith(notes: notes));
    }
  }

  Future<void> _saveRole(String role) async {
    final data = PlayerUpdateData(
      gameName: _player.gameName,
      tagLine:  _player.tagLine,
      role:     role,
      nickname: _player.nickname,
      notes:    _player.notes,
    );
    final err = await ref.read(playersProvider.notifier).updatePlayer(_player.id, data);
    if (err != null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(err, style: const TextStyle(color: Colors.white)),
          backgroundColor: const Color(0xFF5A1A1A),
        ),
      );
    } else {
      setState(() => _player = _player.copyWith(role: role));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBgColor,
      body: Column(
        children: [
          const HextechHeader(title: 'Player'),
          _DetailHeader(
            player:           _player,
            onSaveNotes:      _saveNotes,
            onSaveRole:       _saveRole,
            onRefreshed:      (p) => setState(() => _player = p),
            isAutoRefreshing: _autoRefreshing,
          ),
          Expanded(
            child: LayoutBuilder(builder: (context, constraints) {
              if (constraints.maxWidth < 600) {
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
                          Tab(text: 'MATCHES'),
                          Tab(text: 'CHAMPIONS'),
                          Tab(text: 'SNAPSHOTS'),
                        ],
                      ),
                      Expanded(
                        child: TabBarView(
                          children: [
                            MatchHistoryPanel(playerId: _player.id),
                            SingleChildScrollView(
                              child: ChampionStatsPanel(playerId: _player.id),
                            ),
                            SnapshotPanel(playerId: _player.id),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 3, child: MatchHistoryPanel(playerId: _player.id)),
                  Container(width: 1, color: kBorderColor.withValues(alpha: 0.4)),
                  SizedBox(
                    width: 340,
                    child: Column(
                      children: [
                        ChampionStatsPanel(playerId: _player.id),
                        Container(height: 1, color: kBorderColor.withValues(alpha: 0.4)),
                        Expanded(child: SnapshotPanel(playerId: _player.id)),
                      ],
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

// ── Header de detalle del jugador ─────────────────────────────────────────────

class _DetailHeader extends ConsumerStatefulWidget {
  const _DetailHeader({
    required this.player,
    required this.onSaveNotes,
    required this.onSaveRole,
    required this.onRefreshed,
    this.isAutoRefreshing = false,
  });

  final Player  player;
  final void Function(String) onSaveNotes;
  final Future<void> Function(String) onSaveRole;
  final void Function(Player) onRefreshed;
  final bool isAutoRefreshing;

  @override
  ConsumerState<_DetailHeader> createState() => _DetailHeaderState();
}

class _DetailHeaderState extends ConsumerState<_DetailHeader>
    with SingleTickerProviderStateMixin {
  bool _editingNotes = false;
  bool _refreshing   = false;
  bool _savingRole   = false;
  late final TextEditingController _notesCtrl;
  late final FocusNode             _notesFocus;
  late final AnimationController   _fillCtrl;
  final _roleChipKey  = GlobalKey();
  OverlayEntry? _rolePickerOverlay;

  @override
  void initState() {
    super.initState();
    _notesCtrl  = TextEditingController(text: widget.player.notes);
    _notesFocus = FocusNode();
    _fillCtrl   = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 20),
    );
  }

  @override
  void didUpdateWidget(_DetailHeader oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isAutoRefreshing && !oldWidget.isAutoRefreshing) {
      _fillCtrl.repeat();
    } else if (!widget.isAutoRefreshing && oldWidget.isAutoRefreshing) {
      _fillCtrl.reset();
    }
  }

  @override
  void dispose() {
    _rolePickerOverlay?.remove();
    _notesCtrl.dispose();
    _notesFocus.dispose();
    _fillCtrl.dispose();
    super.dispose();
  }

  // ── Móvil: dialog centrado para seleccionar rol ───────────────────────────
  void _showMobileRolePicker(String currentRole) {
    showDialog<void>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.55),
      builder: (dialogCtx) {
        Widget roleOption(String role) {
          final isSelected = role == currentRole;
          return GestureDetector(
            onTap: () {
              Navigator.of(dialogCtx).pop();
              if (role != currentRole) {
                setState(() => _savingRole = true);
                widget.onSaveRole(role).then((_) {
                  if (mounted) setState(() => _savingRole = false);
                });
              }
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 120),
              width: 80,
              height: 80,
              margin: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: isSelected ? kPrimary.withValues(alpha: 0.2) : Colors.transparent,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: isSelected ? kPrimary.withValues(alpha: 0.5) : kBorderColor.withValues(alpha: 0.3),
                ),
              ),
              child: Center(
                child: RoleChip(role: role, isPrimary: isSelected, size: 32, showLabel: true),
              ),
            ),
          );
        }

        return Dialog(
          backgroundColor: kSurfaceColor,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: kPrimary.withValues(alpha: 0.25)),
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'ROLE',
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: kMuted, letterSpacing: 1.5),
                ),
                const SizedBox(height: 14),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: ['TOP', 'JUNGLE', 'MID'].map(roleOption).toList(),
                ),
                const SizedBox(height: 4),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: ['BOTTOM', 'SUPPORT'].map(roleOption).toList(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ── Móvil: modal centrado para editar notas ───────────────────────────────
  void _showNotesModal() {
    _notesCtrl.text = widget.player.notes;
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
                style: const TextStyle(fontSize: 12, color: kForeground),
                decoration: const InputDecoration(
                  hintText: 'Tactical notes...',
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
                        _notesCtrl.text = widget.player.notes;
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
                        widget.onSaveNotes(_notesCtrl.text.trim());
                        Navigator.of(dialogCtx).pop();
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

  void _showRolePicker() {
    if (_rolePickerOverlay != null) {
      _rolePickerOverlay!.remove();
      _rolePickerOverlay = null;
      return;
    }

    final box = _roleChipKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null) return;
    final overlayBox = Overlay.of(context).context.findRenderObject() as RenderBox;
    final pos        = box.localToGlobal(Offset.zero, ancestor: overlayBox);
    final chipSize   = box.size;
    final chipCenterX = pos.dx + chipSize.width / 2;

    _rolePickerOverlay = OverlayEntry(
      builder: (_) => Stack(
        children: [
          Positioned.fill(
            child: GestureDetector(
              onTap: _dismissRolePicker,
              behavior: HitTestBehavior.opaque,
              child: const SizedBox.expand(),
            ),
          ),
          Positioned(
            top:  pos.dy + chipSize.height + 6,
            left: chipCenterX,
            child: FractionalTranslation(
              translation: const Offset(-0.5, 0),
              child: RolePickerPopup(
                currentRole: widget.player.role,
                onSelected: (role) async {
                  _dismissRolePicker();
                  if (role != widget.player.role) {
                    setState(() => _savingRole = true);
                    await widget.onSaveRole(role);
                    if (mounted) setState(() => _savingRole = false);
                  }
                },
              ),
            ),
          ),
        ],
      ),
    );

    Overlay.of(context).insert(_rolePickerOverlay!);
  }

  void _dismissRolePicker() {
    _rolePickerOverlay?.remove();
    _rolePickerOverlay = null;
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    _fillCtrl.forward(from: 0);

    final err = await ref.read(playersProvider.notifier).refreshPlayer(widget.player.id);

    final updated = ref.read(playersProvider).valueOrNull
        ?.firstWhere((p) => p.id == widget.player.id, orElse: () => widget.player);
    if (updated != null && mounted) widget.onRefreshed(updated);

    ref.invalidate(snapshotsProvider(widget.player.id));
    ref.invalidate(playerMatchesProvider(widget.player.id));

    try {
      await ref.read(matchRepositoryProvider).listForPlayer(
        widget.player.id,
        sync: true,
      );
      ref.invalidate(playerMatchesProvider(widget.player.id));
      await ref.read(playerMatchesProvider(widget.player.id).future);
      await ref.read(snapshotsProvider(widget.player.id).future);
    } catch (_) {}

    if (!mounted) return;
    await _fillCtrl.animateTo(1.0, duration: const Duration(milliseconds: 300));
    await Future.delayed(const Duration(milliseconds: 200));
    _fillCtrl.reset();
    setState(() => _refreshing = false);

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(
        err ?? 'Player updated successfully.',
        style: const TextStyle(color: Colors.white, fontSize: 13),
      ),
      backgroundColor: err != null ? const Color(0xFF5A1A1A) : const Color(0xFF1A3A2A),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(
          color: err != null
              ? Colors.red.withValues(alpha: 0.4)
              : kStatGreen.withValues(alpha: 0.4),
        ),
      ),
    ));
  }

  Widget _buildUpdateButton() => AnimatedBuilder(
    animation: _fillCtrl,
    builder: (_, _) => Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1A0A2E),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: kPrimaryLight.withValues(alpha: 0.3)),
        boxShadow: [BoxShadow(color: kPrimary.withValues(alpha: 0.2), blurRadius: 14)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(7),
        child: Stack(
          children: [
            Positioned.fill(
              child: FractionallySizedBox(
                alignment: Alignment.centerLeft,
                widthFactor: (_refreshing || widget.isAutoRefreshing) ? _fillCtrl.value : 1.0,
                child: Container(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF8A45D4), Color(0xFF6B2E99)],
                    ),
                  ),
                ),
              ),
            ),
            Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: (_refreshing || widget.isAutoRefreshing) ? null : _refresh,
                mouseCursor: (_refreshing || widget.isAutoRefreshing)
                    ? MouseCursor.defer
                    : SystemMouseCursors.click,
                borderRadius: BorderRadius.circular(7),
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  child: Text(
                    'UPDATE',
                    style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 1.2),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );

  Widget _buildNotesWidget({required bool narrow}) {
    final p = widget.player;

    if (narrow) {
      return GestureDetector(
        onTap: _showNotesModal,
        child: Text(
          p.notes.isNotEmpty ? p.notes : 'No notes — tap to add',
          style: TextStyle(
            fontSize: 12,
            fontStyle: FontStyle.italic,
            color: p.notes.isNotEmpty ? kMuted : kMuted.withValues(alpha: 0.4),
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
      );
    }

    // Desktop: edición inline
    if (_editingNotes) {
      return TapRegion(
        onTapOutside: (_) {
          widget.onSaveNotes(_notesCtrl.text.trim());
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
                  hintText: 'Tactical notes...',
                  isDense: true,
                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                ),
              ),
            ),
            const SizedBox(width: 4),
            IconButton(
              icon: const Icon(Icons.check, size: 16, color: kStatGreen),
              onPressed: () {
                widget.onSaveNotes(_notesCtrl.text.trim());
                setState(() => _editingNotes = false);
              },
              constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
              padding: EdgeInsets.zero,
            ),
            IconButton(
              icon: const Icon(Icons.close, size: 16, color: kMuted),
              onPressed: () {
                _notesCtrl.text = widget.player.notes;
                setState(() => _editingNotes = false);
              },
              constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
              padding: EdgeInsets.zero,
            ),
          ],
        ),
      );
    }
    return GestureDetector(
      onTap: () => setState(() => _editingNotes = true),
      child: Text(
        p.notes.isNotEmpty ? p.notes : 'No notes — click to add',
        style: TextStyle(
          fontSize: 12,
          fontStyle: FontStyle.italic,
          color: p.notes.isNotEmpty ? kMuted : kMuted.withValues(alpha: 0.4),
        ),
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p       = widget.player;
    final version = ref.watch(ddragonVersionProvider).valueOrNull;
    final narrow  = MediaQuery.of(context).size.width < 600;

    final wrColor = p.winRate >= 55 ? kStatGold
        : p.winRate >= 50 ? kStatBlue
        : p.winRate >= 45 ? kStatGreen
        : kStatGray;

    // shared avatar widget
    final avatarSize = narrow ? 44.0 : 64.0;
    final avatar = Container(
      width: avatarSize,
      height: avatarSize,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(narrow ? 10 : 14),
        border: Border.all(color: kPrimary.withValues(alpha: 0.4), width: 2),
        boxShadow: [BoxShadow(color: kPrimary.withValues(alpha: 0.2), blurRadius: 14)],
        color: kSurface2,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(narrow ? 8 : 12),
        child: version != null && p.profileIconId > 0
            ? CachedNetworkImage(
                imageUrl: p.profileIconUrl(version),
                fit: BoxFit.cover,
                placeholder: (ctx, url) => Container(
                  color: kSurface2,
                  child: const Center(child: CircularProgressIndicator(strokeWidth: 2, color: kPrimaryLight)),
                ),
                errorWidget: (ctx, url, err) => Icon(Icons.person, color: kMuted, size: narrow ? 26.0 : 32.0),
              )
            : Icon(Icons.person, color: kMuted, size: narrow ? 26.0 : 32.0),
      ),
    );

    // shared role widget
    final roleWidget = _savingRole
        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight))
        : MouseRegion(
            key: _roleChipKey,
            cursor: SystemMouseCursors.click,
            child: GestureDetector(
              onTap: _showRolePicker,
              child: RoleChip(role: p.role, isPrimary: true, size: narrow ? 36.0 : 44.0),
            ),
          );

    if (narrow) {
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
            // Row 1: avatar | name+riotid | UPDATE
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                avatar,
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        p.nickname.isNotEmpty ? p.nickname : p.gameName,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: kForeground),
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Flexible(
                            child: Text(p.riotId, style: const TextStyle(fontSize: 10, color: kMuted), overflow: TextOverflow.ellipsis),
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
                  ),
                ),
                const SizedBox(width: 8),
                _buildUpdateButton(),
              ],
            ),
            const SizedBox(height: 10),
            // Row 2: RankBadge | Spacer | Role | divider | WR(44px)
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                RankBadge(tier: p.tier, division: p.rank, lp: p.lp, region: p.region),
                const Spacer(),
                _savingRole
                    ? const SizedBox(
                        width: 44,
                        height: 44,
                        child: Center(
                          child: SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight),
                          ),
                        ),
                      )
                    : GestureDetector(
                        onTap: () => _showMobileRolePicker(p.role),
                        child: RoleChip(role: p.role, isPrimary: true, size: 44),
                      ),
                Container(
                  width: 1,
                  height: 28,
                  margin: const EdgeInsets.symmetric(horizontal: 8),
                  color: kPrimary.withValues(alpha: 0.25),
                ),
                SizedBox(
                  width: 44,
                  child: p.gamesPlayed > 0
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Text('WR', style: TextStyle(fontSize: 9, color: kMuted, letterSpacing: 1.0)),
                            const SizedBox(height: 3),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(99),
                              child: LinearProgressIndicator(
                                value: (p.winRate / 100).clamp(0.0, 1.0),
                                backgroundColor: kSurface2,
                                color: wrColor,
                                minHeight: 3,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              '${p.winRate.toStringAsFixed(1)}%',
                              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: wrColor),
                            ),
                          ],
                        )
                      : const SizedBox(),
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Row 3: notes
            _buildNotesWidget(narrow: true),
          ],
        ),
      );
    }

    // ── Wide layout ─────────────────────────────────────────────────────────
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        border: Border(bottom: BorderSide(color: kBorderColor.withValues(alpha: 0.5))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios, size: 18, color: kMuted),
            onPressed: () => Navigator.of(context).pop(),
            tooltip: 'Back',
          ),
          const SizedBox(width: 12),
          avatar,
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
                    child: Text(p.region, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: kPrimaryLight)),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(width: 40),
          RankBadge(tier: p.tier, division: p.rank, lp: p.lp, region: p.region),
          const SizedBox(width: 32),
          if (p.gamesPlayed > 0)
            SizedBox(
              width: 80,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('${p.winRate.toStringAsFixed(1)}%',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: wrColor)),
                      Text('${p.gamesPlayed}p', style: const TextStyle(fontSize: 10, color: kMuted)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(99),
                    child: LinearProgressIndicator(
                      value: (p.winRate / 100).clamp(0.0, 1.0),
                      backgroundColor: kSurface2,
                      color: wrColor,
                      minHeight: 4,
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(width: 32),
          Tooltip(
            message: 'Change role',
            child: SizedBox(width: 44, height: 44, child: roleWidget),
          ),
          const SizedBox(width: 32),
          Expanded(child: _buildNotesWidget(narrow: false)),
          const SizedBox(width: 12),
          _buildUpdateButton(),
        ],
      ),
    );
  }
}
