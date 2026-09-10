import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../models/snapshot_model.dart';
import '../providers/snapshot_provider.dart';
import '../../../screens/snapshot_detail_screen.dart';

const _kColHeader = TextStyle(
  fontSize: 9,
  letterSpacing: 1.6,
  color: Color(0xFF4A4560),
  fontWeight: FontWeight.w600,
);

class SnapshotPanel extends ConsumerStatefulWidget {
  const SnapshotPanel({super.key, required this.playerId});
  final int playerId;

  @override
  ConsumerState<SnapshotPanel> createState() => _SnapshotPanelState();
}

class _SnapshotPanelState extends ConsumerState<SnapshotPanel> {
  Future<void> _handleCreate() async {
    final result = await showDialog<({DateTimeRange range, String description})>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.6),
      builder: (_) => const _CreateSnapshotDialog(),
    );
    if (result == null || !mounted) return;

    await ref.read(snapshotsProvider(widget.playerId).notifier).create(
      playerId:    widget.playerId,
      dateFrom:    result.range.start,
      dateTo:      result.range.end,
      description: result.description,
    );
  }

  Future<void> _handleDelete(int snapshotId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: kSurfaceColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
        ),
        title: const Text('Delete snapshot', style: TextStyle(color: kForeground, fontSize: 15)),
        content: const Text(
          'Delete this snapshot and all its matches?',
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
    );
    if (confirmed != true) return;
    final err = await ref.read(snapshotsProvider(widget.playerId).notifier).delete(snapshotId);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(
        err ?? 'Snapshot deleted successfully.',
        style: const TextStyle(color: Colors.white),
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

  @override
  Widget build(BuildContext context) {
    final snapshotsAsync = ref.watch(snapshotsProvider(widget.playerId));
    final creating  = ref.watch(snapshotCreatingProvider(widget.playerId));
    final progress  = ref.watch(snapshotCreationProgressProvider(widget.playerId));

    return Column(
      children: [
        // Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: kBorderColor.withValues(alpha: 0.4))),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('SNAPSHOTS', style: _kColHeader),
              if (creating) ...[
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: (progress / 100).clamp(0.0, 1.0)),
                  duration: const Duration(milliseconds: 600),
                  curve: Curves.easeOut,
                  builder: (_, value, _) => Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(99),
                        child: Container(
                          width: 120,
                          height: 8,
                          color: kSurface2,
                          child: FractionallySizedBox(
                            alignment: Alignment.centerLeft,
                            widthFactor: value,
                            child: Container(
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(99),
                                gradient: const LinearGradient(
                                  colors: [kPrimaryDim, kPrimary, kPrimaryLight],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '${(value * 100).round()}%',
                        style: const TextStyle(fontSize: 11, color: kPrimaryLight, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              ],
              Tooltip(
                message: creating ? 'A snapshot is already in progress' : '',
                child: AnimatedOpacity(
                  opacity: creating ? 0.35 : 1.0,
                  duration: const Duration(milliseconds: 200),
                  child: InkWell(
                    onTap: creating ? null : _handleCreate,
                    mouseCursor: creating
                        ? SystemMouseCursors.forbidden
                        : SystemMouseCursors.click,
                    borderRadius: BorderRadius.circular(6),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: kPrimary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: kPrimary.withValues(alpha: 0.3)),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.add, size: 12, color: kPrimaryLight),
                          SizedBox(width: 4),
                          Text('CREATE', style: TextStyle(fontSize: 9, color: kPrimaryLight, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),

        // Lista
        Expanded(
          child: snapshotsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator(color: kPrimary, strokeWidth: 2)),
            error:   (e, _) => Center(child: Text(e.toString(), style: const TextStyle(color: kMuted, fontSize: 12))),
            data: (snapshots) => snapshots.isEmpty
                ? const Center(
                    child: Text(
                      'No snapshots\nCreate one to analyse a period',
                      style: TextStyle(color: kMuted, fontSize: 12),
                      textAlign: TextAlign.center,
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: snapshots.length,
                    itemBuilder: (_, i) => _SnapshotCard(
                      snapshot: snapshots[i],
                      onDelete: () => _handleDelete(snapshots[i].id),
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}

// ── Tarjeta de snapshot ───────────────────────────────────────────────────────

class _SnapshotCard extends ConsumerStatefulWidget {
  const _SnapshotCard({required this.snapshot, required this.onDelete});
  final SnapshotModel snapshot;
  final VoidCallback  onDelete;

  @override
  ConsumerState<_SnapshotCard> createState() => _SnapshotCardState();
}

class _SnapshotCardState extends ConsumerState<_SnapshotCard> {
  bool _editing = false;
  late final TextEditingController _ctrl;
  late final FocusNode             _focusNode;

  @override
  void initState() {
    super.initState();
    _ctrl      = TextEditingController(text: widget.snapshot.description);
    _focusNode = FocusNode();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  String _fmt(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  // ── Móvil: modal centrado para editar descripción ────────────────────────
  void _showEditModal() {
    _ctrl.text = widget.snapshot.description;
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
                'DESCRIPTION',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: kMuted, letterSpacing: 1.5),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _ctrl,
                autofocus: true,
                maxLines: 3,
                style: const TextStyle(fontSize: 13, color: kForeground),
                decoration: const InputDecoration(
                  hintText: 'E.g. Ranked week — May…',
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
                        _ctrl.text = widget.snapshot.description;
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
                        Navigator.of(dialogCtx).pop();
                        _saveDescription();
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

  Future<void> _saveDescription() async {
    final newDesc = _ctrl.text.trim();
    setState(() => _editing = false);
    if (newDesc == widget.snapshot.description) return;
    try {
      await ref.read(snapshotRepositoryProvider).updateDescription(widget.snapshot.id, newDesc);
      ref.invalidate(snapshotsProvider(widget.snapshot.playerId));
    } on DioException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
            e.message ?? 'Error saving description.',
            style: const TextStyle(color: Colors.white),
          ),
          backgroundColor: const Color(0xFF5A1A1A),
          behavior: SnackBarBehavior.floating,
        ));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.snapshot;
    final narrow = MediaQuery.of(context).size.width < 600;

    void startEditing() {
      if (narrow) {
        _showEditModal();
      } else {
        setState(() => _editing = true);
      }
    }

    final inner = MouseRegion(
      cursor: _editing ? MouseCursor.defer : SystemMouseCursors.click,
      child: GestureDetector(
        onTap: _editing ? null : () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => SnapshotDetailScreen(snapshot: s),
          ),
        ),
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: kSurface2.withValues(alpha: 0.7),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: kBorderColor.withValues(alpha: 0.5)),
          ),
          child: Row(
            children: [
              Icon(Icons.history, size: 14, color: kPrimary.withValues(alpha: 0.6)),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (_editing)
                      GestureDetector(
                        onTap: () {},
                        child: TextField(
                          controller: _ctrl,
                          focusNode: _focusNode,
                          autofocus: true,
                          style: const TextStyle(fontSize: 12, color: kForeground, fontWeight: FontWeight.w600),
                          decoration: const InputDecoration(
                            isDense: true,
                            contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                          ),
                        ),
                      )
                    else
                      MouseRegion(
                        cursor: SystemMouseCursors.click,
                        child: GestureDetector(
                          onTap: startEditing,
                          child: Text(
                            s.description.isNotEmpty
                                ? s.description
                                : (narrow ? 'No description — tap to add' : 'No description — click to add'),
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: s.description.isNotEmpty ? kForeground : kMuted,
                              fontStyle: s.description.isEmpty ? FontStyle.italic : FontStyle.normal,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            '${_fmt(s.dateFrom)} → ${_fmt(s.dateTo)}',
                            style: const TextStyle(fontSize: 10, color: kMuted),
                            overflow: TextOverflow.ellipsis,
                            maxLines: 1,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          '· ${s.matchCount} games',
                          style: TextStyle(fontSize: 10, color: kMuted.withValues(alpha: 0.6)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              // Botones: confirm/cancel en modo edición, edit/delete en modo normal
              if (_editing) ...[
                GestureDetector(
                  onTap: () {},
                  child: IconButton(
                    icon: const Icon(Icons.check, size: 14, color: kStatGreen),
                    onPressed: _saveDescription,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                  ),
                ),
                GestureDetector(
                  onTap: () {},
                  child: IconButton(
                    icon: const Icon(Icons.close, size: 14, color: kMuted),
                    onPressed: () {
                      _ctrl.text = widget.snapshot.description;
                      setState(() => _editing = false);
                    },
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                  ),
                ),
              ] else ...[
                GestureDetector(
                  onTap: startEditing,
                  child: MouseRegion(
                    cursor: SystemMouseCursors.click,
                    child: IconButton(
                      icon: Icon(Icons.edit_outlined, size: 13, color: kMuted.withValues(alpha: 0.6)),
                      onPressed: startEditing,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                      hoverColor: kPrimary.withValues(alpha: 0.1),
                    ),
                  ),
                ),
                GestureDetector(
                  onTap: widget.onDelete,
                  child: MouseRegion(
                    cursor: SystemMouseCursors.click,
                    child: IconButton(
                      icon: const Icon(Icons.delete_outline, size: 14, color: kMuted),
                      onPressed: widget.onDelete,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                      hoverColor: Colors.red.withValues(alpha: 0.1),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );

    return _editing
        ? TapRegion(
            onTapOutside: (_) => _saveDescription(),
            child: inner,
          )
        : inner;
  }
}

// ── Diálogo de creación de snapshot ──────────────────────────────────────────

class _CreateSnapshotDialog extends StatefulWidget {
  const _CreateSnapshotDialog();

  @override
  State<_CreateSnapshotDialog> createState() => _CreateSnapshotDialogState();
}

class _CreateSnapshotDialogState extends State<_CreateSnapshotDialog> {
  DateTime? _from;
  DateTime? _to;
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _setThisMonth() {
    final now = DateTime.now();
    setState(() {
      _from = DateTime(now.year, now.month, 1);
      _to   = now;
    });
  }

  void _setLastMonth() {
    final now = DateTime.now();
    setState(() {
      _from = DateTime(now.year, now.month - 1, 1);
      _to   = DateTime(now.year, now.month, 0);
    });
  }

  void _setLast3Months() {
    final now = DateTime.now();
    setState(() {
      _from = DateTime(now.year, now.month - 3, now.day);
      _to   = now;
    });
  }

  Future<void> _pickDate({required bool isFrom}) async {
    final initial = isFrom
        ? (_from ?? DateTime.now())
        : (_to   ?? DateTime.now());
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2021, 6, 16),
      lastDate: DateTime.now(),
      builder: (ctx, child) => Theme(
        data: Theme.of(ctx).copyWith(
          colorScheme: const ColorScheme.dark(
            primary:          kPrimary,
            onPrimary:        Colors.white,
            surface:          kSurfaceColor,
            onSurface:        kForeground,
            secondary:        kPrimaryDim,
            onSecondary:      Colors.white,
            surfaceContainer: kSurface2,
          ),
          datePickerTheme: DatePickerThemeData(
            backgroundColor:         kSurfaceColor,
            headerBackgroundColor:   kPrimaryDim.withValues(alpha: 0.4),
            headerForegroundColor:   kForeground,
            headerHeadlineStyle:     const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: kForeground),
            headerHelpStyle:         const TextStyle(fontSize: 11, color: kMuted, letterSpacing: 1.2),
            weekdayStyle:            const TextStyle(fontSize: 11, color: kMuted),
            dayStyle:                const TextStyle(fontSize: 12, color: kForeground),
            yearStyle:               const TextStyle(fontSize: 12, color: kForeground),
            todayForegroundColor:    WidgetStateProperty.resolveWith((s) =>
                s.contains(WidgetState.selected) ? Colors.white : kPrimaryLight),
            todayBackgroundColor:    WidgetStateProperty.resolveWith((s) =>
                s.contains(WidgetState.selected) ? kPrimary : kPrimary.withValues(alpha: 0.15)),
            todayBorder:             BorderSide(color: kPrimary.withValues(alpha: 0.5)),
            dayBackgroundColor:      WidgetStateProperty.resolveWith((s) =>
                s.contains(WidgetState.selected) ? kPrimary : null),
            dayForegroundColor:      WidgetStateProperty.resolveWith((s) =>
                s.contains(WidgetState.selected) ? Colors.white : kForeground),
            dayOverlayColor:         WidgetStateProperty.all(kPrimary.withValues(alpha: 0.12)),
            yearBackgroundColor:     WidgetStateProperty.resolveWith((s) =>
                s.contains(WidgetState.selected) ? kPrimary : null),
            yearForegroundColor:     WidgetStateProperty.resolveWith((s) {
                if (s.contains(WidgetState.selected)) return Colors.white;
                if (s.contains(WidgetState.disabled)) return kMuted.withValues(alpha: 0.35);
                return kForeground;
              }),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: BorderSide(color: kPrimary.withValues(alpha: 0.3)),
            ),
            cancelButtonStyle: TextButton.styleFrom(foregroundColor: kMuted),
            confirmButtonStyle: TextButton.styleFrom(foregroundColor: kPrimaryLight),
            inputDecorationTheme: InputDecorationTheme(
              filled: true,
              fillColor: kSurface2,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: kBorderColor),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: kPrimary, width: 1.5),
              ),
            ),
          ),
          textButtonTheme: TextButtonThemeData(
            style: TextButton.styleFrom(foregroundColor: kPrimaryLight),
          ),
        ),
        child: child!,
      ),
    );
    if (picked == null) return;
    setState(() {
      if (isFrom) { _from = picked; } else { _to = picked; }
    });
  }

  String _fmt(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  bool get _valid => _from != null && _to != null && !_from!.isAfter(_to!);
  bool get _datesConflict => _from != null && _to != null && _from!.isAfter(_to!);

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Dialog(
      backgroundColor: kSurfaceColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: kPrimary.withValues(alpha: 0.25)),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: EdgeInsets.all(narrow ? 16 : 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [

              // ── Título ────────────────────────────────────────────────
              const Text(
                'New Snapshot',
                style: TextStyle(color: kForeground, fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 2),
              const Text(
                'Select the period to analyse',
                style: TextStyle(color: kMuted, fontSize: 12),
              ),
              const SizedBox(height: 20),
              Container(height: 1, decoration: BoxDecoration(
                gradient: LinearGradient(colors: [
                  Colors.transparent,
                  kPrimary.withValues(alpha: 0.3),
                  Colors.transparent,
                ]),
              )),
              const SizedBox(height: 20),

              // ── Accesos rápidos ───────────────────────────────────────
              const Text('QUICK SELECT',
                  style: TextStyle(fontSize: 9, letterSpacing: 1.5, color: kMuted, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(child: _QuickChip(label: 'This month',    onTap: _setThisMonth)),
                    const SizedBox(width: 6),
                    Expanded(child: _QuickChip(label: 'Last month',    onTap: _setLastMonth)),
                    const SizedBox(width: 6),
                    Expanded(child: _QuickChip(label: 'Last 3 months', onTap: _setLast3Months)),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // ── Campos de fecha ───────────────────────────────────────
              const Text('PERIOD',
                  style: TextStyle(fontSize: 9, letterSpacing: 1.5, color: kMuted, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _DateField(
                      label: 'From',
                      value: _from != null ? _fmt(_from!) : null,
                      onTap: () => _pickDate(isFrom: true),
                      hasError: _datesConflict,
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    child: Icon(Icons.arrow_forward, size: 14,
                        color: _datesConflict ? Colors.redAccent : kMuted),
                  ),
                  Expanded(
                    child: _DateField(
                      label: 'To',
                      value: _to != null ? _fmt(_to!) : null,
                      onTap: () => _pickDate(isFrom: false),
                      hasError: _datesConflict,
                    ),
                  ),
                ],
              ),
              if (_datesConflict) ...[
                const SizedBox(height: 6),
                const Text(
                  'Start date must be before end date.',
                  style: TextStyle(color: Colors.redAccent, fontSize: 11),
                ),
              ],
              const SizedBox(height: 20),

              // ── Descripción ───────────────────────────────────────────
              const Text('DESCRIPTION (OPTIONAL)',
                  style: TextStyle(fontSize: 9, letterSpacing: 1.5, color: kMuted, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextField(
                controller: _ctrl,
                style: const TextStyle(color: kForeground, fontSize: 13),
                decoration: const InputDecoration(
                  hintText: 'E.g. Ranked week — May…',
                ),
              ),
              const SizedBox(height: 28),

              // ── Acciones ──────────────────────────────────────────────
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Cancel', style: TextStyle(color: kMuted)),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _valid
                        ? () => Navigator.of(context).pop((
                              range: DateTimeRange(start: _from!, end: _to!),
                              description: _ctrl.text.trim(),
                            ))
                        : null,
                    child: const Text('Create snapshot'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Chip de acceso rápido ─────────────────────────────────────────────────────

class _QuickChip extends StatelessWidget {
  const _QuickChip({required this.label, required this.onTap});
  final String     label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: kPrimary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: kPrimary.withValues(alpha: 0.25)),
          ),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: kPrimaryLight, fontWeight: FontWeight.w500),
          ),
        ),
      ),
    );
  }
}

// ── Campo de fecha ────────────────────────────────────────────────────────────

class _DateField extends StatelessWidget {
  const _DateField({
    required this.label,
    required this.value,
    required this.onTap,
    this.hasError = false,
  });
  final String       label;
  final String?      value;
  final VoidCallback onTap;
  final bool         hasError;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: kSurface2,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: hasError
                  ? Colors.redAccent.withValues(alpha: 0.6)
                  : value != null
                      ? kPrimary.withValues(alpha: 0.5)
                      : kBorderColor.withValues(alpha: 0.6),
            ),
          ),
          child: Row(
            children: [
              Icon(
                Icons.calendar_today_outlined,
                size: 13,
                color: hasError ? Colors.redAccent : value != null ? kPrimaryLight : kMuted,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label.toUpperCase(),
                      style: const TextStyle(fontSize: 8, letterSpacing: 1.2, color: kMuted),
                    ),
                    Text(
                      value ?? 'Select',
                      overflow: TextOverflow.ellipsis,
                      maxLines: 1,
                      style: TextStyle(
                        fontSize: 12,
                        color: value != null ? kForeground : kMuted,
                        fontWeight: value != null ? FontWeight.w500 : FontWeight.normal,
                      ),
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
