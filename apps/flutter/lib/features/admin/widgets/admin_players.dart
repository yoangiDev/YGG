import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/shimmer.dart';
import '../models/admin_player_model.dart';
import '../providers/admin_provider.dart';

class AdminPlayers extends ConsumerStatefulWidget {
  const AdminPlayers({super.key});

  @override
  ConsumerState<AdminPlayers> createState() => _AdminPlayersState();
}

class _AdminPlayersState extends ConsumerState<AdminPlayers> {
  String         _search   = '';
  final Set<int> _selected = {};

  List<AdminPlayerModel> _filter(List<AdminPlayerModel> players) {
    if (_search.trim().isEmpty) return players;
    final q = _search.toLowerCase();
    return players.where((p) =>
        p.nickname.toLowerCase().contains(q) ||
        p.riotId.toLowerCase().contains(q)   ||
        p.region.toLowerCase().contains(q)   ||
        p.ownerUsername.toLowerCase().contains(q),
    ).toList();
  }

  Future<void> _deleteSelected(List<AdminPlayerModel> filtered) async {
    final toDelete = List<int>.from(_selected);
    setState(() => _selected.clear());
    String? lastErr;
    for (final id in toDelete) {
      lastErr = await ref.read(adminPlayersProvider.notifier).deletePlayer(id);
    }
    if (!mounted) return;
    if (lastErr != null) {
      _snack(lastErr, isError: true);
    } else {
      _snack('${toDelete.length} player${toDelete.length != 1 ? "s" : ""} deleted successfully.');
    }
  }

  void _snack(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg, style: const TextStyle(fontSize: 13, color: Colors.white)),
        backgroundColor: isError ? const Color(0xFF5A1A1A) : const Color(0xFF1A3A2A),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(
            color: isError
                ? Colors.red.withValues(alpha: 0.4)
                : kStatGreen.withValues(alpha: 0.4),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final playersAsync = ref.watch(adminPlayersProvider);

    return playersAsync.when(
      loading: () => const _AdminPlayersSkeleton(),
      error: (err, _) => Center(
        child: Text(err.toString(), style: const TextStyle(color: kMuted)),
      ),
      data: (players) {
        final filtered = _filter(players);

        return Container(
          decoration: BoxDecoration(
            color: kSurfaceColor,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ── Toolbar ──────────────────────────────────────────────────
              _Toolbar(
                search:           _search,
                selectedCount:    _selected.length,
                totalCount:       players.length,
                onSearchChanged:  (q) => setState(() {
                  _search = q;
                  _selected.clear();
                }),
                onDeleteSelected: () => _deleteSelected(filtered),
              ),

              // ── Cabecera de columnas ──────────────────────────────────────
              _TableHeader(
                allSelected: _selected.length == filtered.length && filtered.isNotEmpty,
                onToggleAll: () => setState(() {
                  if (_selected.length == filtered.length) {
                    _selected.clear();
                  } else {
                    _selected.addAll(filtered.map((p) => p.id));
                  }
                }),
              ),

              // ── Filas ─────────────────────────────────────────────────────
              Expanded(
                child: filtered.isEmpty
                    ? const Center(
                        child: Text('No players found',
                            style: TextStyle(color: kMuted, fontSize: 13)),
                      )
                    : ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (_, i) {
                          final p = filtered[i];
                          return _PlayerAdminRow(
                            player:     p,
                            isSelected: _selected.contains(p.id),
                            onToggle: () => setState(() {
                              _selected.contains(p.id)
                                  ? _selected.remove(p.id)
                                  : _selected.add(p.id);
                            }),
                            onDelete: () async {
                              final displayName = p.nickname.isNotEmpty ? p.nickname : p.gameName;
                              final confirmed = await showDialog<bool>(
                                context: context,
                                builder: (ctx) => AlertDialog(
                                  backgroundColor: kSurfaceColor,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                    side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
                                  ),
                                  title: const Text('Delete player',
                                      style: TextStyle(color: kForeground, fontSize: 15)),
                                  content: Text(
                                    'Delete "$displayName"? All their snapshots and matches will also be removed.',
                                    style: const TextStyle(color: kMuted, fontSize: 13),
                                  ),
                                  actions: [
                                    TextButton(
                                      onPressed: () => Navigator.of(ctx).pop(false),
                                      child: const Text('Cancel', style: TextStyle(color: kMuted)),
                                    ),
                                    TextButton(
                                      onPressed: () => Navigator.of(ctx).pop(true),
                                      child: const Text('Delete', style: TextStyle(color: Colors.redAccent)),
                                    ),
                                  ],
                                ),
                              );
                              if (confirmed != true || !mounted) return;
                              setState(() => _selected.remove(p.id));
                              final err = await ref
                                  .read(adminPlayersProvider.notifier)
                                  .deletePlayer(p.id);
                              if (!mounted) return;
                              if (err != null) {
                                _snack(err, isError: true);
                              } else {
                                _snack('Player "$displayName" deleted successfully.');
                              }
                            },
                          );
                        },
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _AdminPlayersSkeleton extends StatelessWidget {
  const _AdminPlayersSkeleton();

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    final hPad = narrow ? 12.0 : 20.0;
    return Container(
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: Shimmer(
        child: Column(
          children: [
            Padding(
              padding: EdgeInsets.symmetric(horizontal: hPad, vertical: 14),
              child: Row(
                children: [
                  ShimmerBox(width: narrow ? 180 : 260, height: 36, radius: 8),
                  const SizedBox(width: 12),
                  const ShimmerBox(width: 80, height: 14),
                ],
              ),
            ),
            Divider(color: kPrimary.withValues(alpha: 0.06), height: 1),
            Expanded(
              child: ListView.builder(
                itemCount: 8,
                itemBuilder: (_, _) => Container(
                  padding: EdgeInsets.symmetric(horizontal: hPad, vertical: 10),
                  child: Row(
                    children: [
                      const ShimmerBox(width: 20, height: 20, radius: 4),
                      const SizedBox(width: 12),
                      const Expanded(flex: 2, child: ShimmerBox(height: 14)),
                      const SizedBox(width: 8),
                      const Expanded(flex: 3, child: ShimmerBox(height: 14)),
                      const SizedBox(width: 8),
                      const Expanded(child: ShimmerBox(height: 14)),
                      if (!narrow) ...[
                        const SizedBox(width: 8),
                        const Expanded(child: ShimmerBox(height: 14)),
                        const SizedBox(width: 8),
                        const Expanded(child: ShimmerBox(height: 14)),
                        const SizedBox(width: 8),
                        const Expanded(child: ShimmerBox(height: 14)),
                      ],
                      const SizedBox(width: 32),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Toolbar ───────────────────────────────────────────────────────────────────

class _Toolbar extends StatelessWidget {
  const _Toolbar({
    required this.search,
    required this.selectedCount,
    required this.totalCount,
    required this.onSearchChanged,
    required this.onDeleteSelected,
  });

  final String   search;
  final int      selectedCount;
  final int      totalCount;
  final void Function(String) onSearchChanged;
  final VoidCallback onDeleteSelected;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    final searchField = TextField(
      onChanged: onSearchChanged,
      style: const TextStyle(color: kForeground, fontSize: 13),
      decoration: InputDecoration(
        hintText: 'Search player or user...',
        prefixIcon: const Icon(Icons.search, size: 16, color: kMuted),
        contentPadding: const EdgeInsets.symmetric(vertical: 8),
        isDense: true,
        filled: true,
        fillColor: kSurface2,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: kBorderColor.withValues(alpha: 0.4)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: kBorderColor.withValues(alpha: 0.4)),
        ),
      ),
    );
    final deleteButton = selectedCount > 0
        ? TextButton.icon(
            onPressed: onDeleteSelected,
            icon: const Icon(Icons.delete_outline, size: 14, color: Colors.redAccent),
            label: Text('Delete ($selectedCount)',
                style: const TextStyle(fontSize: 12, color: Colors.redAccent)),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              backgroundColor: Colors.redAccent.withValues(alpha: 0.08),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ).copyWith(
              mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
            ),
          )
        : null;

    return Container(
      padding: EdgeInsets.symmetric(horizontal: narrow ? 12 : 20, vertical: narrow ? 10 : 14),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: kPrimary.withValues(alpha: 0.08))),
      ),
      child: narrow
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(child: searchField),
                    if (deleteButton != null) ...[const SizedBox(width: 8), deleteButton],
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  '$totalCount players total',
                  style: TextStyle(fontSize: 11, color: kMuted.withValues(alpha: 0.5)),
                ),
              ],
            )
          : Row(
              children: [
                SizedBox(width: 260, child: searchField),
                const SizedBox(width: 12),
                Text(
                  '$totalCount players total',
                  style: TextStyle(fontSize: 11, color: kMuted.withValues(alpha: 0.5)),
                ),
                const Spacer(),
                if (deleteButton != null) ...[deleteButton, const SizedBox(width: 8)],
              ],
            ),
    );
  }
}

// ── Cabecera de columnas ──────────────────────────────────────────────────────

class _TableHeader extends StatelessWidget {
  const _TableHeader({required this.allSelected, required this.onToggleAll});
  final bool         allSelected;
  final VoidCallback onToggleAll;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Container(
      padding: EdgeInsets.symmetric(horizontal: narrow ? 12 : 20, vertical: 8),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: kPrimary.withValues(alpha: 0.06))),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 20,
            child: Checkbox(
              value: allSelected,
              onChanged: (_) => onToggleAll(),
              activeColor: kPrimary,
              side: const BorderSide(color: kMuted),
            ),
          ),
          const SizedBox(width: 12),
          const _Col('User',   2),
          const _Col('Player', 3),
          _Col('Region', 1, textAlign: narrow ? TextAlign.right : TextAlign.start),
          if (!narrow) ...[
            const _Col('Role', 1),
            const _Col('Rank', 1),
            const _Col('LP',   1),
          ],
          const SizedBox(width: 32),
        ],
      ),
    );
  }
}

class _Col extends StatelessWidget {
  const _Col(this.label, this.flex, {this.textAlign = TextAlign.start});
  final String  label;
  final int     flex;
  final TextAlign textAlign;

  @override
  Widget build(BuildContext context) => Expanded(
    flex: flex,
    child: Text(label.toUpperCase(),
        style: const TextStyle(fontSize: 9, letterSpacing: 1.5, color: kMuted),
        textAlign: textAlign),
  );
}

// ── Fila de jugador ───────────────────────────────────────────────────────────

class _PlayerAdminRow extends StatefulWidget {
  const _PlayerAdminRow({
    required this.player,
    required this.isSelected,
    required this.onToggle,
    required this.onDelete,
  });
  final AdminPlayerModel player;
  final bool             isSelected;
  final VoidCallback     onToggle;
  final VoidCallback     onDelete;

  @override
  State<_PlayerAdminRow> createState() => _PlayerAdminRowState();
}

class _PlayerAdminRowState extends State<_PlayerAdminRow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    final p = widget.player;
    final tierLabel = p.tier.isEmpty
        ? '—'
        : p.tier[0] + p.tier.substring(1).toLowerCase();

    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit:  (_) => setState(() => _hovered = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        color: widget.isSelected
            ? kPrimary.withValues(alpha: 0.08)
            : _hovered
                ? kPrimary.withValues(alpha: 0.04)
                : Colors.transparent,
        padding: EdgeInsets.symmetric(horizontal: narrow ? 12 : 20, vertical: 7),
        child: Row(
          children: [
            // Checkbox
            SizedBox(
              width: 20,
              child: Checkbox(
                value: widget.isSelected,
                onChanged: (_) => widget.onToggle(),
                activeColor: kPrimary,
                side: const BorderSide(color: kMuted),
              ),
            ),
            const SizedBox(width: 12),

            // Usuario propietario
            Expanded(
              flex: 2,
              child: Row(
                children: [
                  Container(
                    width: 22, height: 22,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF6B3A9E), Color(0xFF4A2270)],
                      ),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        p.ownerUsername.isNotEmpty
                            ? p.ownerUsername[0].toUpperCase()
                            : '?',
                        style: const TextStyle(
                            fontSize: 10, fontWeight: FontWeight.bold, color: kForeground),
                      ),
                    ),
                  ),
                  const SizedBox(width: 7),
                  Expanded(
                    child: Text(p.ownerUsername,
                      style: const TextStyle(fontSize: 12, color: kMuted),
                      overflow: TextOverflow.ellipsis),
                  ),
                ],
              ),
            ),

            // Jugador
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    p.nickname.isNotEmpty ? p.nickname : p.gameName,
                    style: const TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w600, color: kForeground),
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(p.riotId,
                    style: const TextStyle(fontSize: 10, color: kMuted),
                    overflow: TextOverflow.ellipsis),
                ],
              ),
            ),

            // Región
            Expanded(
              flex: 1,
              child: Text(p.region,
                style: const TextStyle(fontSize: 12, color: kMuted),
                overflow: TextOverflow.ellipsis,
                textAlign: narrow ? TextAlign.right : TextAlign.start),
            ),

            // Rol / Rango / LP — solo desktop
            if (!narrow) ...[
              Expanded(
                flex: 1,
                child: Text(p.role,
                  style: const TextStyle(fontSize: 12, color: kMuted),
                  overflow: TextOverflow.ellipsis),
              ),
              Expanded(
                flex: 1,
                child: Text(
                  p.rank.isNotEmpty ? '$tierLabel ${p.rank}' : tierLabel,
                  style: const TextStyle(fontSize: 12, color: kForeground),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Expanded(
                flex: 1,
                child: Text('${p.lp} LP',
                  style: const TextStyle(fontSize: 12, color: kMuted),
                  overflow: TextOverflow.ellipsis),
              ),
            ],

            // Borrar
            SizedBox(
              width: 32,
              child: AnimatedOpacity(
                duration: const Duration(milliseconds: 120),
                opacity: _hovered ? 1.0 : 0.0,
                child: IconButton(
                  icon: const Icon(Icons.delete_outline, size: 16),
                  color: kMuted,
                  hoverColor: Colors.red.withValues(alpha: 0.1),
                  onPressed: widget.onDelete,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                  tooltip: 'Delete player',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
