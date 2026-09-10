import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme/app_theme.dart';
import '../core/widgets/shimmer.dart';
import '../features/players/models/player.dart';
import '../features/players/providers/players_provider.dart';
import '../features/players/providers/rank_cutoffs_provider.dart';
import '../features/players/providers/snapshot_provider.dart';
import '../features/players/widgets/hextech_header.dart';
import '../features/players/widgets/player_table.dart';
import '../features/players/widgets/add_player_dialog.dart';
import 'player_detail_screen.dart';
import 'rank_cutoffs_screen.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  String _searchQuery = '';
  bool _cutoffsRequested = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refreshRankCutoffs());
  }

  void _refreshRankCutoffs() {
    if (_cutoffsRequested) return;
    _cutoffsRequested = true;

    final players = ref.read(playersProvider).valueOrNull ?? const [];
    final regions = players.map((p) => p.region);
    if (regions.isEmpty) {
      ref.read(rankCutoffsProvider.notifier).refreshRegionsIfStale(const ['EUW']);
      return;
    }
    ref.read(rankCutoffsProvider.notifier).refreshRegionsIfStale(regions);
  }

  void _openRankCutoffsScreen() {
    final players = ref.read(playersProvider).valueOrNull ?? const [];
    final initialRegion = players.isNotEmpty
        ? players.first.region.toUpperCase()
        : 'EUW';
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => RankCutoffsScreen(initialRegion: initialRegion),
      ),
    );
  }

  Future<void> _showAddDialog() async {
    final added = await showDialog<bool>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.6),
      builder: (_) => AddPlayerDialog(
        onAdd: (data) async {
          final err = await ref.read(playersProvider.notifier).addPlayer(data);
          return err;
        },
      ),
    );
    if (added == true && mounted) _showSnackbar('Player added successfully.');
  }

  void _handleDelete(int id) {
    showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: kSurfaceColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
        ),
        title: const Text('Delete player', style: TextStyle(color: kForeground)),
        content: const Text(
          'Are you sure you want to delete this player? All their snapshots and matches will also be removed.',
          style: TextStyle(color: kMuted, fontSize: 13),
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
    ).then((confirmed) async {
      if (confirmed != true) return;
      final err = await ref.read(playersProvider.notifier).deletePlayer(id);
      if (!mounted) return;
      if (err != null) {
        _showSnackbar(err, isError: true);
      } else {
        _showSnackbar('Player deleted successfully.');
      }
    });
  }

  Future<void> _handleRefresh(int id) async {
    final err = await ref.read(playersProvider.notifier).refreshPlayer(id);
    if (err != null && mounted) {
      _showSnackbar(err, isError: true);
    } else if (mounted) {
      _showSnackbar('Player updated successfully.');
    }
  }

  Future<void> _handleEditNotes(int id, String notes) async {
    final player = (ref.read(playersProvider).valueOrNull ?? [])
        .where((p) => p.id == id)
        .firstOrNull;
    if (player == null) return;

    final data = PlayerUpdateData(
      gameName: player.gameName,
      tagLine:  player.tagLine,
      role:     player.role,
      nickname: player.nickname,
      notes:    notes,
    );
    final err = await ref.read(playersProvider.notifier).updatePlayer(id, data);
    if (err != null && mounted) _showSnackbar(err, isError: true);
  }

  Future<void> _handleEditRole(int id, String role) async {
    final player = (ref.read(playersProvider).valueOrNull ?? [])
        .where((p) => p.id == id)
        .firstOrNull;
    if (player == null) return;

    final data = PlayerUpdateData(
      gameName: player.gameName,
      tagLine:  player.tagLine,
      role:     role,
      nickname: player.nickname,
      notes:    player.notes,
    );
    final err = await ref.read(playersProvider.notifier).updatePlayer(id, data);
    if (err != null && mounted) _showSnackbar(err, isError: true);
  }

  void _showSnackbar(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          message,
          style: const TextStyle(
            fontSize: 13,
            color: Colors.white,
          ),
        ),
        backgroundColor: isError ? const Color(0xFF5A1A1A) : const Color(0xFF1A3A2A),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(
            color: isError ? Colors.red.withValues(alpha: 0.4) : kStatGreen.withValues(alpha: 0.4),
          ),
        ),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<SnapshotNotification?>(snapshotNotificationProvider, (_, notification) {
      if (notification == null) return;
      _showSnackbar(notification.message, isError: !notification.isSuccess);
      ref.read(snapshotNotificationProvider.notifier).state = null;
    });

    final playersAsync = ref.watch(playersProvider);

    ref.listen<AsyncValue<List<Player>>>(playersProvider, (prev, next) {
      final prevRegions = prev?.valueOrNull?.map((p) => p.region).toSet() ?? {};
      final nextRegions = next.valueOrNull?.map((p) => p.region).toSet() ?? {};
      if (nextRegions.isNotEmpty &&
          (prev?.valueOrNull == null || !setEquals(prevRegions, nextRegions))) {
        ref.read(rankCutoffsProvider.notifier).refreshRegionsIfStale(nextRegions);
      }
    });

    return Scaffold(
      body: Column(
        children: [
          // Header (con navegación al panel admin para usuarios admin)
          const HextechHeader(title: 'Home Screen', showBackButton: false),

          // Contenido principal
          Expanded(
            child: Stack(
              children: [
                // Fondo sutil
                Positioned.fill(
                  child: CustomPaint(painter: _BackgroundPainter()),
                ),

                // Tabla
                playersAsync.when(
                  loading: () => const _PlayerTableSkeleton(),
                  error: (err, _) => Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline, color: Colors.redAccent, size: 40),
                        const SizedBox(height: 12),
                        Text(
                          err.toString(),
                          style: const TextStyle(color: kMuted, fontSize: 13),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          icon: const Icon(Icons.refresh, size: 16),
                          label: const Text('Retry'),
                          onPressed: () => ref.read(playersProvider.notifier).reload(),
                        ),
                      ],
                    ),
                  ),
                  data: (players) => Padding(
                    padding: EdgeInsets.symmetric(
                      horizontal: MediaQuery.of(context).size.width < 600 ? 8.0 : 32.0,
                      vertical: 24,
                    ),
                    child: PlayerTable(
                      players:         players,
                      isLoading:       false,
                      searchQuery:     _searchQuery,
                      onSearchChanged: (q) => setState(() => _searchQuery = q),
                      onAddPlayer:     _showAddDialog,
                      onOpenRankCutoffs: _openRankCutoffsScreen,
                      onDelete:        _handleDelete,
                      onRefresh:       _handleRefresh,
                      onEditNotes:     _handleEditNotes,
                      onEditRole:      _handleEditRole,
                      onPlayerTap:     (player) => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => PlayerDetailScreen(player: player),
                        ),
                      ),
                    ),
                  ),
                ),

                // Línea decorativa inferior
                Positioned(
                  bottom: 0, left: 0, right: 0,
                  child: Container(
                    height: 1,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [
                        Colors.transparent,
                        kPrimary.withValues(alpha: 0.2),
                        Colors.transparent,
                      ]),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Skeleton de la tabla de jugadores ────────────────────────────────────────

class _PlayerTableSkeleton extends StatelessWidget {
  const _PlayerTableSkeleton();

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: narrow ? 8.0 : 32.0, vertical: 24),
      child: SizedBox.expand(
        child: Container(
          decoration: BoxDecoration(
            color: kSurfaceColor.withValues(alpha: 0.95),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
          ),
          child: Shimmer(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                  child: Row(
                    children: [
                      if (narrow)
                        const Expanded(child: ShimmerBox(height: 36, radius: 8))
                      else
                        const ShimmerBox(width: 280, height: 36, radius: 8),
                      if (!narrow) const Spacer(),
                      if (narrow) const SizedBox(width: 8),
                      const ShimmerBox(width: 110, height: 34, radius: 8),
                    ],
                  ),
                ),
                Divider(color: kPrimary.withValues(alpha: 0.1), height: 1),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: 8,
                    itemBuilder: (_, _) => narrow
                        ? Container(
                            margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                // Fila 1: avatar + nombre/riotid + botones
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.center,
                                  children: [
                                    ShimmerBox(width: 48, height: 48, radius: 10),
                                    SizedBox(width: 10),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          ShimmerBox(height: 14),
                                          SizedBox(height: 4),
                                          ShimmerBox(height: 10),
                                        ],
                                      ),
                                    ),
                                    SizedBox(width: 8),
                                    ShimmerBox(width: 56, height: 24, radius: 6),
                                    SizedBox(width: 5),
                                    ShimmerBox(width: 48, height: 24, radius: 6),
                                  ],
                                ),
                                SizedBox(height: 7),
                                // Fila 2: rango (tamaño natural) | Spacer | rol | línea | WR
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.center,
                                  children: [
                                    ShimmerBox(width: 44, height: 44, radius: 6),
                                    SizedBox(width: 10),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        ShimmerBox(width: 80, height: 13),
                                        SizedBox(height: 5),
                                        ShimmerBox(width: 60, height: 4, radius: 2),
                                      ],
                                    ),
                                    Spacer(),
                                    ShimmerBox(width: 44, height: 44, radius: 8),
                                    SizedBox(width: 8),
                                    ShimmerBox(width: 1, height: 28),
                                    SizedBox(width: 8),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.end,
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        ShimmerBox(width: 20, height: 9),
                                        SizedBox(height: 3),
                                        ShimmerBox(width: 38, height: 12),
                                      ],
                                    ),
                                  ],
                                ),
                                SizedBox(height: 7),
                                // Fila 3: notas
                                ShimmerBox(height: 11),
                              ],
                            ),
                          )
                        : Container(
                            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            child: Row(
                              children: [
                                const ShimmerBox(width: 48, height: 48, radius: 10),
                                const SizedBox(width: 16),
                                SizedBox(
                                  width: 180,
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisSize: MainAxisSize.min,
                                    children: const [
                                      ShimmerBox(width: 120, height: 13),
                                      SizedBox(height: 5),
                                      ShimmerBox(width: 80, height: 11),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 16),
                                const SizedBox(
                                  width: 80,
                                  child: Center(child: ShimmerBox(width: 56, height: 24, radius: 12)),
                                ),
                                const SizedBox(width: 16),
                                const Expanded(child: ShimmerBox(height: 12)),
                                const SizedBox(width: 16),
                                const SizedBox(width: 180, child: ShimmerBox(height: 36, radius: 8)),
                                const SizedBox(width: 16),
                                SizedBox(
                                  width: 80,
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.end,
                                    mainAxisSize: MainAxisSize.min,
                                    children: const [
                                      ShimmerBox(width: 48, height: 16),
                                      SizedBox(height: 6),
                                      ShimmerBox(height: 4),
                                      SizedBox(height: 4),
                                      ShimmerBox(width: 52, height: 10),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
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

// ── Fondo con efecto sutil ────────────────────────────────────────────────────

class _BackgroundPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0.7, -0.5),
        colors: [
          kPrimary.withValues(alpha: 0.04),
          Colors.transparent,
        ],
        radius: 0.8,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paint);
  }

  @override
  bool shouldRepaint(_) => false;
}
