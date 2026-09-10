import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../models/player.dart';

const _regions = ['EUW', 'EUNE', 'TR', 'RU', 'NA', 'LAN', 'LAS', 'BR'];
const _roles   = ['TOP', 'JUNGLE', 'MID', 'BOTTOM', 'SUPPORT'];
const _roleLabels = {
  'TOP': 'Top', 'JUNGLE': 'Jungle',
  'MID': 'Mid', 'BOTTOM': 'Bot', 'SUPPORT': 'Support',
};
const _roleAssets = {
  'TOP':     'assets/roles/top.png',
  'JUNGLE':  'assets/roles/jungle.png',
  'MID':     'assets/roles/middle.png',
  'BOTTOM':  'assets/roles/bottom.png',
  'SUPPORT': 'assets/roles/support.png',
};

class AddPlayerDialog extends StatefulWidget {
  const AddPlayerDialog({super.key, required this.onAdd});

  final Future<String?> Function(PlayerCreateData) onAdd;

  @override
  State<AddPlayerDialog> createState() => _AddPlayerDialogState();
}

class _AddPlayerDialogState extends State<AddPlayerDialog> {
  final _formKey = GlobalKey<FormState>();
  final _gameNameCtrl = TextEditingController();
  final _tagLineCtrl  = TextEditingController();
  final _nicknameCtrl = TextEditingController();
  final _notesCtrl    = TextEditingController();

  String _region   = 'EUW';
  String _role     = 'TOP';
  bool   _loading  = false;
  String? _error;

  @override
  void dispose() {
    _gameNameCtrl.dispose();
    _tagLineCtrl.dispose();
    _nicknameCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _loading = true; _error = null; });

    final data = PlayerCreateData(
      gameName: _gameNameCtrl.text.trim(),
      tagLine:  _tagLineCtrl.text.trim(),
      region:   _region,
      nickname: _nicknameCtrl.text.trim(),
      role:     _role,
      notes:    _notesCtrl.text.trim(),
    );

    final err = await widget.onAdd(data);

    if (!mounted) return;
    if (err != null) {
      setState(() { _loading = false; _error = err; });
    } else {
      Navigator.of(context).pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;

    return Dialog(
      backgroundColor: kSurfaceColor,
      insetPadding: EdgeInsets.symmetric(
        horizontal: narrow ? 16 : 40,
        vertical:   narrow ? 24 : 40,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: SingleChildScrollView(
          child: Padding(
          padding: EdgeInsets.all(narrow ? 20 : 28),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Título ───────────────────────────────────────────────────
                Text(
                  'NEW PLAYER',
                  style: TextStyle(
                    color: kPrimaryLight,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 2.5,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  height: 1,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: [
                      kPrimary.withValues(alpha: 0.6),
                      kPrimary.withValues(alpha: 0.2),
                      Colors.transparent,
                    ]),
                  ),
                ),
                const SizedBox(height: 20),

                // ── Game Name + Tag ──────────────────────────────────────────
                Row(children: [
                  Expanded(child: _field(
                    controller: _gameNameCtrl,
                    label: 'Game Name *',
                    hint: 'Faker',
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                  )),
                  const SizedBox(width: 12),
                  SizedBox(
                    width: 100,
                    child: _field(
                      controller: _tagLineCtrl,
                      label: 'Tag *',
                      hint: 'KR1',
                      validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                    ),
                  ),
                ]),
                const SizedBox(height: 12),

                // ── Nickname ─────────────────────────────────────────────────
                _field(controller: _nicknameCtrl, label: 'Nickname (optional)', hint: 'The boss'),
                const SizedBox(height: 12),

                // ── Región ──────────────────────────────────────────────────
                _dropdown(
                  label: 'Region *',
                  value: _region,
                  items: _regions,
                  onChanged: (v) => setState(() => _region = v!),
                ),
                const SizedBox(height: 12),

                // ── Rol ──────────────────────────────────────────────────────
                _roleSelector(),
                const SizedBox(height: 12),

                // ── Notas ────────────────────────────────────────────────────
                _field(
                  controller: _notesCtrl,
                  label: 'Tactical notes (optional)',
                  hint: 'Good objective control...',
                  maxLines: 3,
                ),
                const SizedBox(height: 20),

                // ── Error ────────────────────────────────────────────────────
                if (_error != null) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
                    ),
                    child: Text(_error!, style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
                  ),
                  const SizedBox(height: 16),
                ],

                // ── Botones ──────────────────────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: _loading ? null : () => Navigator.of(context).pop(),
                      child: const Text('Cancel', style: TextStyle(color: kMuted)),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton(
                      onPressed: _loading ? null : _submit,
                      child: _loading
                          ? const SizedBox(
                              width: 16, height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Text('CONFIRM', style: TextStyle(letterSpacing: 1.5, fontSize: 12)),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        ),
      ),
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required String hint,
    int maxLines = 1,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: kMuted, fontSize: 10, letterSpacing: 1.2)),
        const SizedBox(height: 4),
        TextFormField(
          controller: controller,
          maxLines: maxLines,
          validator: validator,
          style: const TextStyle(color: kForeground, fontSize: 13),
          decoration: InputDecoration(hintText: hint),
        ),
      ],
    );
  }

  Widget _roleSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Role', style: TextStyle(color: kMuted, fontSize: 10, letterSpacing: 1.2)),
        const SizedBox(height: 8),
        Row(
          children: _roles.map((role) {
            final selected = _role == role;
            final asset = _roleAssets[role];
            return Expanded(
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                onTap: () => setState(() => _role = role),
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    color: selected
                        ? kPrimary.withValues(alpha: 0.2)
                        : kSurface2,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: selected
                          ? kPrimary.withValues(alpha: 0.5)
                          : kBorderColor.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (asset != null)
                        Image.asset(
                          asset,
                          width: 22,
                          height: 22,
                          color: selected ? kPrimaryLight : kMuted,
                        )
                      else
                        Icon(Icons.grid_view_rounded, size: 22,
                            color: selected ? kPrimaryLight : kMuted),
                      const SizedBox(height: 4),
                      Text(
                        _roleLabels[role] ?? role,
                        style: TextStyle(
                          fontSize: 10,
                          color: selected ? kPrimaryLight : kMuted,
                          fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _dropdown({
    required String label,
    required String value,
    required List<String> items,
    Map<String, String>? labelMap,
    required void Function(String?) onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: kMuted, fontSize: 10, letterSpacing: 1.2)),
        const SizedBox(height: 4),
        LayoutBuilder(
          builder: (_, constraints) => PopupMenuButton<String>(
            initialValue: value,
            onSelected: (v) => onChanged(v),
            offset: const Offset(0, 40),
            color: kSurface2,
            constraints: BoxConstraints(minWidth: constraints.maxWidth, maxWidth: constraints.maxWidth, maxHeight: 260),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
              side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
            ),
            itemBuilder: (_) => items.map((v) => PopupMenuItem(
              value: v,
              child: Text(labelMap?[v] ?? v,
                style: const TextStyle(color: kForeground, fontSize: 13)),
            )).toList(),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: kSurface2,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: kBorderColor),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(labelMap?[value] ?? value,
                    style: const TextStyle(color: kForeground, fontSize: 13)),
                  const Icon(Icons.arrow_drop_down, size: 18, color: kMuted),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
