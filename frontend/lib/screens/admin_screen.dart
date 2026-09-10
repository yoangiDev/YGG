import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme/app_theme.dart';
import '../features/players/widgets/hextech_header.dart';
import '../features/admin/widgets/admin_stats.dart';
import '../features/admin/widgets/admin_players.dart';
import '../features/admin/widgets/admin_users.dart';

enum _AdminTab { stats, players, users }

class AdminScreen extends ConsumerStatefulWidget {
  const AdminScreen({super.key});

  @override
  ConsumerState<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends ConsumerState<AdminScreen> {
  _AdminTab _active = _AdminTab.stats;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          const HextechHeader(showAdminLink: false, title: 'Admin'),

          // ── Contenido ─────────────────────────────────────────────────
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: const Alignment(-0.6, -0.4),
                  colors: [kPrimary.withValues(alpha: 0.04), Colors.transparent],
                  radius: 0.7,
                ),
              ),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ── Cabecera fija (volver + tabs centradas) ────────
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                      child: Column(
                        children: [
                          Builder(builder: (ctx) {
                            final narrow = MediaQuery.of(ctx).size.width < 600;
                            return Row(
                              children: [
                                if (!narrow) ...[
                                  IconButton(
                                    icon: const Icon(Icons.arrow_back_ios_new,
                                        size: 16, color: kMuted),
                                    onPressed: () => Navigator.of(context).pop(),
                                    tooltip: 'Back',
                                    padding: EdgeInsets.zero,
                                    constraints: const BoxConstraints(
                                        minWidth: 32, minHeight: 32),
                                  ),
                                ],
                                Expanded(
                                  child: Center(
                                    child: _TabBar(
                                      active: _active,
                                      onChanged: (t) =>
                                          setState(() => _active = t),
                                    ),
                                  ),
                                ),
                                if (!narrow) const SizedBox(width: 32),
                              ],
                            );
                          }),
                          const SizedBox(height: 12),
                        ],
                      ),
                    ),

                    // ── Contenido expandible por tab ───────────────────
                    Expanded(
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 160),
                        child: KeyedSubtree(
                          key: ValueKey(_active),
                          child: switch (_active) {
                            _AdminTab.stats => Builder(builder: (ctx) {
                              final h = MediaQuery.of(ctx).size.width < 600 ? 12.0 : 32.0;
                              return SingleChildScrollView(
                                padding: EdgeInsets.fromLTRB(h, 0, h, 24),
                                child: const AdminStats(),
                              );
                            }),
                            _AdminTab.players => Builder(builder: (ctx) {
                              final h = MediaQuery.of(ctx).size.width < 600 ? 6.0 : 12.0;
                              return Padding(
                                padding: EdgeInsets.fromLTRB(h, 0, h, h),
                                child: const AdminPlayers(),
                              );
                            }),
                            _AdminTab.users => Builder(builder: (ctx) {
                              final h = MediaQuery.of(ctx).size.width < 600 ? 6.0 : 12.0;
                              return Padding(
                                padding: EdgeInsets.fromLTRB(h, 0, h, h),
                                child: const AdminUsers(),
                              );
                            }),
                          },
                        ),
                      ),
                    ),
                  ],
                ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Barra de tabs ─────────────────────────────────────────────────────────────

class _TabBar extends StatelessWidget {
  const _TabBar({required this.active, required this.onChanged});
  final _AdminTab                  active;
  final void Function(_AdminTab t) onChanged;

  static const _tabs = [
    _TabDef(_AdminTab.stats,   Icons.bar_chart_outlined,    'Stats'),
    _TabDef(_AdminTab.players, Icons.manage_search_outlined, 'Players'),
    _TabDef(_AdminTab.users,   Icons.people_outline,         'Users'),
  ];

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: const Color(0xFF0F0D18),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: _tabs.map((t) {
          final isActive = active == t.tab;
          return MouseRegion(
            cursor: SystemMouseCursors.click,
            child: GestureDetector(
            onTap: () => onChanged(t.tab),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              padding: EdgeInsets.symmetric(horizontal: narrow ? 10.0 : 18.0, vertical: 8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(7),
                gradient: isActive
                    ? const LinearGradient(
                        colors: [Color(0xFF8B48D4), Color(0xFF6B2FA0)],
                      )
                    : null,
                boxShadow: isActive
                    ? [
                        BoxShadow(
                          color: kPrimary.withValues(alpha: 0.3),
                          blurRadius: 10,
                        )
                      ]
                    : null,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(t.icon, size: 15,
                      color: isActive ? Colors.white : kMuted),
                  const SizedBox(width: 7),
                  Text(
                    t.label,
                    style: TextStyle(
                      fontSize: 13,
                      color: isActive ? Colors.white : kMuted,
                      fontWeight:
                          isActive ? FontWeight.w600 : FontWeight.normal,
                    ),
                  ),
                ],
              ),
            ),
          ),
          );
        }).toList(),
      ),
    );
  }
}

// ── Datos de tab ──────────────────────────────────────────────────────────────

class _TabDef {
  const _TabDef(this.tab, this.icon, this.label);
  final _AdminTab tab;
  final IconData  icon;
  final String    label;
}

