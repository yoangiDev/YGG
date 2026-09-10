import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../models/player.dart';
import '../providers/ddragon_provider.dart';
import 'rank_badge.dart';
import 'role_chip.dart';

class PlayerRow extends StatefulWidget {
  const PlayerRow({
    super.key,
    required this.player,
    required this.onDelete,
    required this.onRefresh,
    required this.onEditNotes,
    required this.onEditRole,
    this.onTap,
  });

  final Player  player;
  final VoidCallback onDelete;
  final Future<void> Function() onRefresh;
  final void Function(String notes) onEditNotes;
  final Future<void> Function(String role) onEditRole;
  final VoidCallback? onTap;

  @override
  State<PlayerRow> createState() => _PlayerRowState();
}

class _PlayerRowState extends State<PlayerRow> {
  bool _hovered      = false;
  bool _editingNotes = false;
  bool _savingRole   = false;
  bool _refreshing   = false;
  late final TextEditingController _notesCtrl;
  final _roleChipKey = GlobalKey();
  OverlayEntry? _rolePickerOverlay;

  @override
  void initState() {
    super.initState();
    _notesCtrl = TextEditingController(text: widget.player.notes);
  }

  @override
  void didUpdateWidget(PlayerRow old) {
    super.didUpdateWidget(old);
    if (old.player.notes != widget.player.notes) {
      _notesCtrl.text = widget.player.notes;
    }
  }

  @override
  void dispose() {
    _rolePickerOverlay?.remove();
    _notesCtrl.dispose();
    super.dispose();
  }

  void _showRolePicker() {
    if (_rolePickerOverlay != null) {
      _rolePickerOverlay!.remove();
      _rolePickerOverlay = null;
      return;
    }

    final box = _roleChipKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null) return;
    final overlayBox  = Overlay.of(context).context.findRenderObject() as RenderBox;
    final pos         = box.localToGlobal(Offset.zero, ancestor: overlayBox);
    final chipSize    = box.size;
    final chipCenterX = pos.dx + chipSize.width / 2;

    const popupH     = 70.0; // estimated height of the role picker row
    final spaceBelow = overlayBox.size.height - pos.dy - chipSize.height;
    final showAbove  = spaceBelow < popupH + 10;
    final topPos     = showAbove
        ? pos.dy - popupH - 6
        : pos.dy + chipSize.height + 6;

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
            top:  topPos,
            left: chipCenterX,
            child: FractionalTranslation(
              translation: const Offset(-0.5, 0),
              child: RolePickerPopup(
                currentRole: widget.player.role,
                onSelected: (role) async {
                  _dismissRolePicker();
                  if (role != widget.player.role) {
                    setState(() => _savingRole = true);
                    await widget.onEditRole(role);
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

  void _saveNotes() {
    widget.onEditNotes(_notesCtrl.text);
    setState(() => _editingNotes = false);
  }

  void _cancelNotes() {
    _notesCtrl.text = widget.player.notes;
    setState(() => _editingNotes = false);
  }

  Color _wrTextColor(double wr) {
    if (wr >= 55) return kStatGold;
    if (wr >= 50) return kStatBlue;
    if (wr >= 45) return kStatGreen;
    return kStatGray;
  }

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    final p = widget.player;
    return narrow ? _buildNarrow(p) : _buildWide(p);
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
                widget.onEditRole(role).then((_) {
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

  // ── Móvil: spinner mientras refresca ─────────────────────────────────────
  Future<void> _handleNarrowRefresh() async {
    setState(() => _refreshing = true);
    await widget.onRefresh();
    if (mounted) setState(() => _refreshing = false);
  }

  // ── Móvil: modal centrado para editar notas ───────────────────────────────
  void _showNotesModal(Player p) {
    _notesCtrl.text = p.notes;
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
                        _notesCtrl.text = p.notes;
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
                        widget.onEditNotes(_notesCtrl.text);
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

  // ── Móvil: notas (toca para abrir modal) ─────────────────────────────────
  Widget _buildNarrowNotes(Player p) {
    return GestureDetector(
      onTap: () => _showNotesModal(p),
      child: Text(
        p.notes.isNotEmpty ? p.notes : 'No notes — tap to add',
        style: TextStyle(
          fontSize: 10,
          fontStyle: FontStyle.italic,
          color: p.notes.isNotEmpty ? kMuted : kMuted.withValues(alpha: 0.35),
        ),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }

  // ── Móvil: botón de acción con etiqueta ───────────────────────────────────
  Widget _buildActionButton(String label, Color color, VoidCallback onPressed) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withValues(alpha: 0.35)),
        ),
        child: Text(
          label,
          style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: color, letterSpacing: 0.6),
        ),
      ),
    );
  }

  Widget _buildNarrow(Player p) {
    return GestureDetector(
      onTap: widget.onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
        decoration: BoxDecoration(
          color: kSurfaceColor.withValues(alpha: 0.6),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: kBorderColor.withValues(alpha: 0.15)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Fila 1: avatar | nombre + riotid | Refresh Delete
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                _ProfileIcon(player: p),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        p.nickname.isNotEmpty ? p.nickname : p.gameName,
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: kForeground),
                        overflow: TextOverflow.ellipsis,
                        maxLines: 1,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Flexible(
                            child: Text(p.riotId, style: const TextStyle(fontSize: 10, color: kMuted), overflow: TextOverflow.ellipsis, maxLines: 1),
                          ),
                          const SizedBox(width: 4),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                            decoration: BoxDecoration(
                              color: kPrimary.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(p.region, style: const TextStyle(fontSize: 8, fontWeight: FontWeight.bold, color: kPrimaryLight)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                _refreshing
                    ? const SizedBox(
                        width: 56,
                        height: 24,
                        child: Center(
                          child: SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight),
                          ),
                        ),
                      )
                    : _buildActionButton('Refresh', kPrimaryLight, _handleNarrowRefresh),
                const SizedBox(width: 5),
                _buildActionButton('Delete', Colors.redAccent, widget.onDelete),
              ],
            ),
            const SizedBox(height: 7),
            // Fila 2: RankBadge (tamaño natural) — Spacer — Rol | línea | WR
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                RankBadge(tier: p.tier, division: p.rank, lp: p.lp, region: p.region),
                const Spacer(),
                _savingRole
                    ? const SizedBox(width: 32, height: 32, child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight))
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
                            Text(
                              '${p.winRate.toStringAsFixed(1)}%',
                              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: _wrTextColor(p.winRate)),
                            ),
                          ],
                        )
                      : const SizedBox(),
                ),
              ],
            ),
            const SizedBox(height: 5),
            // Fila 3: notas editables inline — ancho completo
            _buildNarrowNotes(p),
          ],
        ),
      ),
    );
  }

  Widget _buildWide(Player p) {
    return MouseRegion(
      onEnter:  (_) => setState(() => _hovered = true),
      onExit:   (_) => setState(() => _hovered = false),
      cursor: widget.onTap != null ? SystemMouseCursors.click : MouseCursor.defer,
      child: GestureDetector(
        onTap: _editingNotes ? null : widget.onTap,
        child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: _hovered
              ? const Color(0xFF1F1B30).withValues(alpha: 0.9)
              : kSurfaceColor.withValues(alpha: 0.6),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: _hovered
                ? kPrimary.withValues(alpha: 0.25)
                : kBorderColor.withValues(alpha: 0.15),
          ),
        ),
        child: Row(
          children: [
            _ProfileIcon(player: p),
            const SizedBox(width: 16),
            SizedBox(
              width: 180,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    p.nickname.isNotEmpty ? p.nickname : p.gameName,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kForeground),
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Flexible(
                        child: Text(p.riotId, style: const TextStyle(fontSize: 11, color: kMuted), overflow: TextOverflow.ellipsis),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          color: kPrimary.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(p.region, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: kPrimaryLight)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 16),
            SizedBox(
              width: 80,
              child: Center(
                child: _savingRole
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 1.5, color: kPrimaryLight))
                    : Tooltip(
                        message: 'Change role',
                        child: MouseRegion(
                          key: _roleChipKey,
                          cursor: SystemMouseCursors.click,
                          child: GestureDetector(
                            onTap: _showRolePicker,
                            behavior: HitTestBehavior.opaque,
                            child: RoleChip(role: p.role, isPrimary: true),
                          ),
                        ),
                      ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _editingNotes
                  ? Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _notesCtrl,
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
                          onPressed: _saveNotes,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close, size: 16, color: kMuted),
                          onPressed: _cancelNotes,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                        ),
                      ],
                    )
                  : MouseRegion(
                      cursor: SystemMouseCursors.click,
                      child: GestureDetector(
                        onTap: () => setState(() => _editingNotes = true),
                        child: Text(
                          p.notes.isNotEmpty ? p.notes : 'No notes — click to add',
                          style: TextStyle(
                            fontSize: 12,
                            color: p.notes.isNotEmpty ? kMuted : kMuted.withValues(alpha: 0.4),
                            fontStyle: FontStyle.italic,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
            ),
            const SizedBox(width: 16),
            SizedBox(
              width: 200,
              child: RankBadge(tier: p.tier, division: p.rank, lp: p.lp, region: p.region, lpOnly: true),
            ),
            const SizedBox(width: 16),
            SizedBox(
              width: 80,
              child: _WinRateCell(winRate: p.winRate, gamesPlayed: p.gamesPlayed),
            ),
            const SizedBox(width: 12),
            AnimatedOpacity(
              opacity: _hovered ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 150),
              child: Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.refresh, size: 16),
                    color: kMuted,
                    hoverColor: kPrimary.withValues(alpha: 0.1),
                    tooltip: 'Refresh player',
                    onPressed: widget.onRefresh,
                    constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                    padding: EdgeInsets.zero,
                  ),
                  const SizedBox(width: 2),
                  IconButton(
                    icon: const Icon(Icons.delete_outline, size: 16),
                    color: kMuted,
                    hoverColor: Colors.red.withValues(alpha: 0.1),
                    tooltip: 'Delete player',
                    onPressed: widget.onDelete,
                    constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                    padding: EdgeInsets.zero,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      ),
    );
  }
}

// ── Widget auxiliar: icono de perfil ──────────────────────────────────────────

class _ProfileIcon extends ConsumerWidget {
  const _ProfileIcon({required this.player});
  final Player player;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final version = ref.watch(ddragonVersionProvider).valueOrNull;
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kPrimary.withValues(alpha: 0.35), width: 2),
        boxShadow: [
          BoxShadow(color: kPrimary.withValues(alpha: 0.15), blurRadius: 10),
        ],
        color: kSurface2,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: version != null && player.profileIconId > 0
            ? CachedNetworkImage(
                imageUrl: player.profileIconUrl(version),
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
                errorWidget: (ctx, err, stack) => const _IconPlaceholder(),
              )
            : const _IconPlaceholder(),
      ),
    );
  }
}

class _IconPlaceholder extends StatelessWidget {
  const _IconPlaceholder();

  @override
  Widget build(BuildContext context) => const Center(
    child: Icon(Icons.person, color: kMuted, size: 22),
  );
}

// ── Widget auxiliar: win rate ─────────────────────────────────────────────────

class _WinRateCell extends StatelessWidget {
  const _WinRateCell({required this.winRate, required this.gamesPlayed});
  final double winRate;
  final int    gamesPlayed;

  Color get _textColor {
    if (winRate >= 55) return kStatGold;
    if (winRate >= 50) return kStatBlue;
    if (winRate >= 45) return kStatGreen;
    return kStatGray;
  }

  Color get _barColor {
    if (winRate >= 55) return kStatGold;
    if (winRate >= 50) return kStatBlue;
    if (winRate >= 45) return kStatGreen;
    return kStatGray;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '${winRate.toStringAsFixed(1)}%',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            height: 1.0,
            color: _textColor,
          ),
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: LinearProgressIndicator(
            value: (winRate / 100).clamp(0.0, 1.0),
            backgroundColor: kSurface2,
            color: _barColor,
            minHeight: 4,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '$gamesPlayed games',
          style: const TextStyle(fontSize: 10, color: kMuted),
        ),
      ],
    );
  }
}
