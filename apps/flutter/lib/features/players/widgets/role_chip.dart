import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

const _roleLabels = <String, String>{
  'TOP':     'Top',
  'JUNGLE':  'Jungle',
  'MID':     'Mid',
  'BOTTOM':  'Bot',
  'SUPPORT': 'Support',
};

const _roleAssets = <String, String>{
  'TOP':     'assets/roles/top.png',
  'JUNGLE':  'assets/roles/jungle.png',
  'MID':     'assets/roles/middle.png',
  'BOTTOM':  'assets/roles/bottom.png',
  'SUPPORT': 'assets/roles/support.png',
};

class RoleChip extends StatelessWidget {
  const RoleChip({
    super.key,
    required this.role,
    this.isPrimary = true,
    this.size      = 32,
    this.showLabel = false,
  });

  final String role;
  final bool   isPrimary;
  final double size;
  final bool   showLabel;

  @override
  Widget build(BuildContext context) {
    final key   = role.toUpperCase();
    final label = _roleLabels[key] ?? role;
    final asset = _roleAssets[key];
    final color = isPrimary ? kPrimaryLight : kMuted;

    final icon = asset != null
        ? Image.asset(asset, width: size, height: size, color: color)
        : Icon(Icons.grid_view_rounded, size: size, color: color);

    if (!showLabel) return icon;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        icon,
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color),
        ),
      ],
    );
  }
}

// ── Popup selector de rol (reutilizable) ──────────────────────────────────────

class _RoleOption extends StatefulWidget {
  const _RoleOption({required this.role, required this.isSelected, required this.onTap});
  final String       role;
  final bool         isSelected;
  final VoidCallback onTap;

  @override
  State<_RoleOption> createState() => _RoleOptionState();
}

class _RoleOptionState extends State<_RoleOption> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final active = widget.isSelected || _hovered;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hovered = true),
        onExit:  (_) => setState(() => _hovered = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 120),
            width: 60,
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: widget.isSelected
                  ? kPrimary.withValues(alpha: 0.2)
                  : _hovered
                      ? kPrimary.withValues(alpha: 0.1)
                      : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: active
                    ? kPrimary.withValues(alpha: 0.5)
                    : Colors.transparent,
              ),
            ),
            child: RoleChip(role: widget.role, isPrimary: active, size: 28, showLabel: true),
          ),
        ),
      ),
    );
  }
}

class RolePickerPopup extends StatelessWidget {
  const RolePickerPopup({super.key, required this.currentRole, required this.onSelected});
  final String currentRole;
  final void Function(String) onSelected;

  static const _roles = ['TOP', 'JUNGLE', 'MID', 'BOTTOM', 'SUPPORT'];

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        decoration: BoxDecoration(
          color: kSurfaceColor,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: kPrimary.withValues(alpha: 0.3)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.35),
              blurRadius: 16,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: _roles.map((role) => _RoleOption(
            role:       role,
            isSelected: role == currentRole,
            onTap:      () => onSelected(role),
          )).toList(),
        ),
      ),
    );
  }
}
