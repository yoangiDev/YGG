import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../models/player.dart';
import 'player_row.dart';

class PlayerTable extends StatelessWidget {
  const PlayerTable({
    super.key,
    required this.players,
    required this.isLoading,
    required this.searchQuery,
    required this.onSearchChanged,
    required this.onAddPlayer,
    required this.onDelete,
    required this.onRefresh,
    required this.onEditNotes,
    required this.onEditRole,
    this.onPlayerTap,
    this.onOpenRankCutoffs,
  });

  final List<Player> players;
  final bool         isLoading;
  final String       searchQuery;
  final void Function(String) onSearchChanged;
  final VoidCallback           onAddPlayer;
  final void Function(int)     onDelete;
  final Future<void> Function(int) onRefresh;
  final void Function(int, String) onEditNotes;
  final Future<void> Function(int, String) onEditRole;
  final void Function(Player)?     onPlayerTap;
  final VoidCallback?              onOpenRankCutoffs;

  List<Player> get _filtered {
    if (searchQuery.trim().isEmpty) return players;
    final q = searchQuery.toLowerCase();
    return players.where((p) =>
      p.gameName.toLowerCase().contains(q) ||
      p.nickname.toLowerCase().contains(q) ||
      p.riotId.toLowerCase().contains(q) ||
      p.tier.toLowerCase().contains(q)
    ).toList();
  }

  @override
  Widget build(BuildContext context) {
    final visible = _filtered;
    final isEmpty = !isLoading && visible.isEmpty;

    return SizedBox.expand(
      child: Container(
      decoration: BoxDecoration(
        color: kSurfaceColor.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.4),
            blurRadius: 32,
            offset: const Offset(0, 4),
          ),
          BoxShadow(
            color: kPrimary.withValues(alpha: 0.04),
            blurRadius: 0,
            spreadRadius: 1,
          ),
        ],
      ),
      child: Column(
        children: [
          // ── Barra de herramientas ──────────────────────────────────────────
          _Toolbar(
            searchQuery:     searchQuery,
            onSearchChanged: onSearchChanged,
            playerCount:     players.length,
            onAddPlayer:     onAddPlayer,
            onOpenRankCutoffs: onOpenRankCutoffs,
          ),

          // ── Cabecera de columnas ───────────────────────────────────────────
          if (!isLoading && !isEmpty && MediaQuery.of(context).size.width >= 600)
            const _ColumnHeader(),

          // ── Contenido (scrollable) ─────────────────────────────────────────
          Expanded(
            child: isLoading
                ? const Center(
                    child: CircularProgressIndicator(color: kPrimary, strokeWidth: 2),
                  )
                : isEmpty
                    ? _EmptyState(onAddPlayer: onAddPlayer, hasSearch: searchQuery.isNotEmpty)
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemCount: visible.length,
                        itemBuilder: (context, i) => PlayerRow(
                          key:         ValueKey(visible[i].id),
                          player:      visible[i],
                          onDelete:    () => onDelete(visible[i].id),
                          onRefresh:   () => onRefresh(visible[i].id),
                          onEditNotes: (notes) => onEditNotes(visible[i].id, notes),
                          onEditRole:  (role)  => onEditRole(visible[i].id, role),
                          onTap:       onPlayerTap != null ? () => onPlayerTap!(visible[i]) : null,
                        ),
                      ),
          ),
        ],
      ),
    ));
  }
}

// ── Toolbar ──────────────────────────────────────────────────────────────────

class _Toolbar extends StatelessWidget {
  const _Toolbar({
    required this.searchQuery,
    required this.onSearchChanged,
    required this.playerCount,
    required this.onAddPlayer,
    this.onOpenRankCutoffs,
  });

  final String    searchQuery;
  final void Function(String) onSearchChanged;
  final int       playerCount;
  final VoidCallback onAddPlayer;
  final VoidCallback? onOpenRankCutoffs;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    final searchField = SizedBox(
      height: 36,
      child: TextField(
        onChanged: onSearchChanged,
        style: const TextStyle(color: kForeground, fontSize: 13),
        decoration: InputDecoration(
          hintText: 'Search player, rank...',
          prefixIcon: const Icon(Icons.search, size: 16, color: kMuted),
          prefixIconConstraints: const BoxConstraints(minWidth: 36, minHeight: 36),
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        ),
      ),
    );

    final actionRow = Row(
      mainAxisSize: narrow ? MainAxisSize.max : MainAxisSize.min,
      children: [
        if (playerCount > 0) ...[
          Text(
            '$playerCount player${playerCount != 1 ? "s" : ""}',
            style: TextStyle(fontSize: 11, color: kMuted.withValues(alpha: 0.5)),
          ),
          const SizedBox(width: 10),
        ],
        if (narrow) const Spacer(),
        if (onOpenRankCutoffs != null) ...[
          _SecondaryButton(
            label: 'CUTOFFS',
            icon: Icons.leaderboard_outlined,
            onPressed: onOpenRankCutoffs!,
          ),
          const SizedBox(width: 8),
        ],
        _AddButton(onPressed: onAddPlayer),
      ],
    );

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: narrow ? 12 : 20,
        vertical: narrow ? 10 : 14,
      ),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: kPrimary.withValues(alpha: 0.1))),
      ),
      child: narrow
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                searchField,
                const SizedBox(height: 8),
                actionRow,
              ],
            )
          : Row(
              children: [
                SizedBox(width: 280, child: searchField),
                const Spacer(),
                if (playerCount > 0) ...[
                  Text(
                    '$playerCount player${playerCount != 1 ? "s" : ""}',
                    style: TextStyle(fontSize: 11, color: kMuted.withValues(alpha: 0.5)),
                  ),
                  const SizedBox(width: 16),
                ],
                if (onOpenRankCutoffs != null) ...[
                  _SecondaryButton(
                    label: 'LP CUTOFFS',
                    icon: Icons.leaderboard_outlined,
                    onPressed: onOpenRankCutoffs!,
                  ),
                  const SizedBox(width: 10),
                ],
                _AddButton(onPressed: onAddPlayer),
              ],
            ),
    );
  }
}

class _AddButton extends StatelessWidget {
  const _AddButton({required this.onPressed});
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF8A45D4), Color(0xFF6B2E99)],
        ),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: kPrimaryLight.withValues(alpha: 0.2)),
        boxShadow: [
          BoxShadow(color: kPrimary.withValues(alpha: 0.3), blurRadius: 14),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          mouseCursor: SystemMouseCursors.click,
          borderRadius: BorderRadius.circular(8),
          child: const Padding(
            padding: EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.add, size: 15, color: Colors.white),
                SizedBox(width: 6),
                Text(
                  'ADD PLAYER',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SecondaryButton extends StatelessWidget {
  const _SecondaryButton({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: kSurface2,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onPressed,
        mouseCursor: SystemMouseCursors.click,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: kBorderColor.withValues(alpha: 0.5)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 15, color: kPrimaryLight),
              const SizedBox(width: 6),
              Text(
                label,
                style: const TextStyle(
                  color: kPrimaryLight,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.1,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Cabecera de columnas ──────────────────────────────────────────────────────

class _ColumnHeader extends StatelessWidget {
  const _ColumnHeader();

  @override
  Widget build(BuildContext context) {
    const style = TextStyle(
      fontSize: 9,
      letterSpacing: 1.8,
      color: Color(0xFF4A4560),
      fontWeight: FontWeight.w600,
    );
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 8),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: kPrimary.withValues(alpha: 0.07))),
      ),
      child: const Row(
        children: [
          SizedBox(width: 48 + 16),
          SizedBox(width: 180, child: Text('PLAYER', style: style)),
          SizedBox(width: 16),
          SizedBox(width: 80,  child: Text('ROLE', style: style, textAlign: TextAlign.center)),
          SizedBox(width: 16),
          Expanded(            child: Text('NOTES',   style: style)),
          SizedBox(width: 16),
          SizedBox(width: 180, child: Text('RANK', style: style)),
          SizedBox(width: 16),
          SizedBox(width: 80,  child: Text('WR',    style: style, textAlign: TextAlign.end)),
          SizedBox(width: 56 + 12),
        ],
      ),
    );
  }
}

// ── Estado vacío ──────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.onAddPlayer, required this.hasSearch});
  final VoidCallback onAddPlayer;
  final bool hasSearch;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 80),
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: kPrimary.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: kPrimary.withValues(alpha: 0.15)),
            ),
            child: const Icon(Icons.group_outlined, color: kMuted, size: 28),
          ),
          const SizedBox(height: 16),
          Text(
            hasSearch ? 'No results' : 'No Players',
            style: const TextStyle(
              color: kForeground,
              fontSize: 15,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.5,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            hasSearch
                ? 'No players match your search.'
                : 'Add players to start tracking their performance.',
            style: TextStyle(color: kMuted.withValues(alpha: 0.7), fontSize: 13),
          ),
          if (!hasSearch) ...[
            const SizedBox(height: 20),
            _AddButton(onPressed: onAddPlayer),
          ],
        ],
      ),
    );
  }
}
