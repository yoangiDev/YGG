import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/shimmer.dart';
import '../../../core/auth/auth_provider.dart';
import '../models/app_user.dart';
import '../providers/admin_provider.dart';

class AdminUsers extends ConsumerStatefulWidget {
  const AdminUsers({super.key});

  @override
  ConsumerState<AdminUsers> createState() => _AdminUsersState();
}

class _AdminUsersState extends ConsumerState<AdminUsers> {
  bool _showForm = false;

  final _emailCtrl    = TextEditingController();
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  String  _newRole    = 'user';
  bool    _creating   = false;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _handleCreate() async {
    if (_emailCtrl.text.isEmpty ||
        _usernameCtrl.text.isEmpty ||
        _passwordCtrl.text.isEmpty) { return; }
    if (_passwordCtrl.text.length < 6) {
      _snack('Password must be at least 6 characters.', isError: true);
      return;
    }

    setState(() => _creating = true);

    final err = await ref.read(adminUsersProvider.notifier).createUser(
      email:    _emailCtrl.text.trim(),
      username: _usernameCtrl.text.trim(),
      password: _passwordCtrl.text,
      role:     _newRole,
    );

    if (!mounted) return;
    setState(() => _creating = false);
    if (err != null) {
      _snack(err, isError: true);
    } else {
      _emailCtrl.clear();
      _usernameCtrl.clear();
      _passwordCtrl.clear();
      setState(() => _newRole = 'user');
      _snack('User created successfully.');
    }
  }

  void _snack(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg, style: const TextStyle(color: Colors.white, fontSize: 13)),
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

  Future<void> _handleDeleteInactive() async {
    final users = ref.read(adminUsersProvider).valueOrNull ?? [];
    final inactiveCount = users.where((u) => !u.isActive).length;

    if (inactiveCount == 0) {
      _snack('No inactive accounts to remove.');
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: kSurfaceColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
        ),
        title: const Text('Remove inactive accounts',
            style: TextStyle(color: kForeground, fontSize: 15)),
        content: Text(
          '$inactiveCount inactive account${inactiveCount != 1 ? "s" : ""} will be removed along with all their players and snapshots. This action cannot be undone.',
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

    final (err, count) = await ref.read(adminUsersProvider.notifier).deleteInactiveUsers();
    if (!mounted) return;
    if (err != null) {
      _snack(err, isError: true);
    } else {
      _snack('$count inactive account${count != 1 ? "s" : ""} removed.');
    }
  }

  void _openNewUserDialog() async {
    final created = await showDialog<bool>(
      context: context,
      builder: (_) => const _NewUserMobileDialog(),
    );
    if (created == true && mounted) _snack('User created successfully.');
  }

  @override
  Widget build(BuildContext context) {
    final usersAsync = ref.watch(adminUsersProvider);
    final narrow = MediaQuery.of(context).size.width < 600;

    final userList = Container(
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _ListToolbar(
            formOpen: narrow ? false : _showForm,
            onToggleForm: narrow
                ? _openNewUserDialog
                : () => setState(() => _showForm = !_showForm),
            onDeleteInactive: _handleDeleteInactive,
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: kPrimary.withValues(alpha: 0.06))),
            ),
            child: narrow
                ? const Row(
                    children: [
                      Expanded(flex: 2, child: _ColHeader('User')),
                      Expanded(child: _ColHeader('Role',   textAlign: TextAlign.center)),
                      Expanded(child: _ColHeader('Status', textAlign: TextAlign.right)),
                    ],
                  )
                : const Row(
                    children: [
                      Expanded(child: _ColHeader('User')),
                      Expanded(child: _ColHeader('Email')),
                      Expanded(child: _ColHeader('Role')),
                      Expanded(child: _ColHeader('Status')),
                    ],
                  ),
          ),
          Expanded(
            child: usersAsync.when(
              loading: () => const _UserListSkeleton(),
              error: (err, _) => Center(
                child: Text(err.toString(), style: const TextStyle(color: kMuted, fontSize: 13)),
              ),
              data: (users) {
                final currentUsername = ref.read(authProvider).username;
                return users.isEmpty
                    ? const Center(child: Text('No users', style: TextStyle(color: kMuted, fontSize: 13)))
                    : ListView.builder(
                        itemCount: users.length,
                        itemBuilder: (_, i) => _UserRow(
                          user:   users[i],
                          isSelf: users[i].username == currentUsername,
                          narrow: narrow,
                          onRoleChanged: (role) async {
                            final err = await ref.read(adminUsersProvider.notifier).updateRole(users[i].id, role);
                            if (err != null && mounted) _snack(err);
                          },
                          onToggleActive: () async {
                            final err = await ref.read(adminUsersProvider.notifier).toggleActive(users[i].id);
                            if (err != null && mounted) _snack(err, isError: true);
                          },
                          // En móvil onDelete es directo (el long-press ya confirmó).
                          // En desktop onDelete muestra el dialog de confirmación.
                          onDelete: narrow
                              ? () async {
                                  final username = users[i].username;
                                  final err = await ref
                                      .read(adminUsersProvider.notifier)
                                      .deleteUser(users[i].id);
                                  if (!mounted) return;
                                  if (err != null) {
                                    _snack(err, isError: true);
                                  } else {
                                    _snack('User "$username" deleted successfully.');
                                  }
                                }
                              : () async {
                                  final confirmed = await showDialog<bool>(
                                    context: context,
                                    builder: (ctx) => AlertDialog(
                                      backgroundColor: kSurfaceColor,
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(12),
                                        side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
                                      ),
                                      title: const Text('Delete user',
                                          style: TextStyle(color: kForeground, fontSize: 15)),
                                      content: Text(
                                        'Delete "${users[i].username}"? All their players and snapshots will also be removed.',
                                        style: const TextStyle(color: kMuted, fontSize: 13),
                                      ),
                                      actions: [
                                        TextButton(
                                          onPressed: () => Navigator.of(ctx).pop(false),
                                          child: const Text('Cancel', style: TextStyle(color: kMuted)),
                                        ),
                                        TextButton(
                                          onPressed: () => Navigator.of(ctx).pop(true),
                                          child: const Text('Delete',
                                              style: TextStyle(color: Colors.redAccent)),
                                        ),
                                      ],
                                    ),
                                  );
                                  if (confirmed != true) return;
                                  final username = users[i].username;
                                  final err = await ref
                                      .read(adminUsersProvider.notifier)
                                      .deleteUser(users[i].id);
                                  if (!mounted) return;
                                  if (err != null) {
                                    _snack(err, isError: true);
                                  } else {
                                    _snack('User "$username" deleted successfully.');
                                  }
                                },
                        ),
                      );
              },
            ),
          ),
        ],
      ),
    );

    if (narrow) return userList;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(child: userList),
        AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeInOut,
          width: _showForm ? 300.0 : 0.0,
          clipBehavior: Clip.hardEdge,
          decoration: const BoxDecoration(),
          child: OverflowBox(
            minWidth: 300,
            maxWidth: 300,
            alignment: Alignment.topLeft,
            child: SizedBox(
              width: 300,
              child: _SideFormPanel(
                emailCtrl:    _emailCtrl,
                usernameCtrl: _usernameCtrl,
                passwordCtrl: _passwordCtrl,
                role:         _newRole,
                creating:     _creating,
                onRoleChanged: (v) => setState(() => _newRole = v),
                onSubmit:      _handleCreate,
                onClose: () => setState(() => _showForm = false),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _UserListSkeleton extends StatelessWidget {
  const _UserListSkeleton();

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    final hPad = narrow ? 12.0 : 20.0;
    return Shimmer(
      child: ListView.builder(
        itemCount: 8,
        itemBuilder: (_, _) => Container(
          padding: EdgeInsets.symmetric(horizontal: hPad, vertical: 10),
          child: narrow
              ? Row(
                  children: const [
                    // User (flex:2)
                    Expanded(flex: 2, child: ShimmerBox(height: 14)),
                    SizedBox(width: 12),
                    // Role chip — ancho fijo igual que el chip real
                    ShimmerBox(width: 72, height: 28, radius: 8),
                    SizedBox(width: 12),
                    // Status badge — alineado a la derecha
                    ShimmerBox(width: 64, height: 22, radius: 6),
                  ],
                )
              : Row(
                  children: const [
                    Expanded(child: ShimmerBox(height: 14)),
                    SizedBox(width: 16),
                    Expanded(child: ShimmerBox(height: 14)),
                    SizedBox(width: 16),
                    Expanded(child: ShimmerBox(width: 52, height: 22, radius: 11)),
                    SizedBox(width: 16),
                    Expanded(child: ShimmerBox(width: 60, height: 22, radius: 11)),
                  ],
                ),
        ),
      ),
    );
  }
}

// ── Toolbar de la lista ───────────────────────────────────────────────────────

class _ListToolbar extends StatelessWidget {
  const _ListToolbar({
    required this.formOpen,
    required this.onToggleForm,
    required this.onDeleteInactive,
  });
  final bool         formOpen;
  final VoidCallback onToggleForm;
  final VoidCallback onDeleteInactive;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    return Container(
      padding: EdgeInsets.symmetric(horizontal: narrow ? 12 : 20, vertical: 14),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: kPrimary.withValues(alpha: 0.08))),
      ),
      child: Row(
        children: [
          if (!narrow)
            const Text(
              'USERS',
              style: TextStyle(
                fontSize: 10,
                letterSpacing: 1.8,
                color: kMuted,
                fontWeight: FontWeight.w600,
              ),
            ),
          const Spacer(),
          // En móvil solo icono para "Clear inactive"
          narrow
              ? IconButton(
                  onPressed: onDeleteInactive,
                  icon: const Icon(Icons.delete_sweep_outlined, size: 18, color: kMuted),
                  tooltip: 'Clear inactive',
                  padding: const EdgeInsets.all(8),
                  constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                  style: IconButton.styleFrom(
                    backgroundColor: kSurface2,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                )
              : TextButton.icon(
                  onPressed: onDeleteInactive,
                  icon: const Icon(Icons.delete_sweep_outlined, size: 15, color: kMuted),
                  label: const Text('Clear inactive',
                      style: TextStyle(fontSize: 12, color: kMuted)),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    backgroundColor: kSurface2,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ).copyWith(
                    mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
                  ),
                ),
          const SizedBox(width: 8),
          TextButton.icon(
            onPressed: onToggleForm,
            icon: Icon(
              formOpen ? Icons.close : Icons.person_add_outlined,
              size: 15,
              color: formOpen ? kMuted : Colors.white,
            ),
            label: Text(
              formOpen ? 'Close' : 'New User',
              style: TextStyle(fontSize: 12, color: formOpen ? kMuted : Colors.white),
            ),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              backgroundColor: formOpen ? kSurface2 : kPrimary,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ).copyWith(
              mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Panel lateral del formulario ──────────────────────────────────────────────

class _SideFormPanel extends StatelessWidget {
  const _SideFormPanel({
    required this.emailCtrl,
    required this.usernameCtrl,
    required this.passwordCtrl,
    required this.role,
    required this.creating,
    required this.onRoleChanged,
    required this.onSubmit,
    required this.onClose,
  });

  final TextEditingController emailCtrl;
  final TextEditingController usernameCtrl;
  final TextEditingController passwordCtrl;
  final String               role;
  final bool                 creating;
  final void Function(String) onRoleChanged;
  final VoidCallback          onSubmit;
  final VoidCallback          onClose;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(left: 12),
      decoration: BoxDecoration(
        color: kSurfaceColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kPrimary.withValues(alpha: 0.12)),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Cabecera del panel
            Row(
              children: [
                const Icon(Icons.person_add_outlined, size: 16, color: kPrimary),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'NEW USER',
                    style: TextStyle(
                      fontSize: 10,
                      letterSpacing: 1.8,
                      color: kMuted,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 16, color: kMuted),
                  onPressed: onClose,
                  padding: EdgeInsets.zero,
                  constraints:
                      const BoxConstraints(minWidth: 24, minHeight: 24),
                ),
              ],
            ),

            Container(
              height: 1,
              margin: const EdgeInsets.symmetric(vertical: 16),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [
                  kPrimary.withValues(alpha: 0.5),
                  Colors.transparent,
                ]),
              ),
            ),

            // Campos
            _Field(controller: emailCtrl,    label: 'Email',    hint: 'user@example.com'),
            const SizedBox(height: 12),
            _Field(controller: usernameCtrl, label: 'Username', hint: 'username'),
            const SizedBox(height: 12),
            _Field(controller: passwordCtrl, label: 'Password', hint: '••••••••', obscure: true),
            const SizedBox(height: 12),

            // Rol
            const Text(
              'ROLE',
              style: TextStyle(
                fontSize: 9, letterSpacing: 1.5, color: kMuted, fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 6),
            LayoutBuilder(
              builder: (context, constraints) => PopupMenuButton<String>(
                initialValue: role,
                onSelected: onRoleChanged,
                offset: const Offset(0, 42),
                color: kSurface2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                  side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
                ),
                constraints: BoxConstraints(
                  minWidth: constraints.maxWidth,
                  maxWidth: constraints.maxWidth,
                ),
                itemBuilder: (_) => const [
                  PopupMenuItem(
                    value: 'user',
                    child: Text('User', style: TextStyle(color: kForeground, fontSize: 13)),
                  ),
                  PopupMenuItem(
                    value: 'admin',
                    child: Text('Admin', style: TextStyle(color: kForeground, fontSize: 13)),
                  ),
                ],
                child: Container(
                  height: 40,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: kSurface2,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: kBorderColor),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        role == 'admin' ? 'Admin' : 'User',
                        style: const TextStyle(color: kForeground, fontSize: 13),
                      ),
                      const Icon(Icons.arrow_drop_down, size: 16, color: kMuted),
                    ],
                  ),
                ),
              ),
            ),

            const SizedBox(height: 20),

            // Botón crear
            SizedBox(
              height: 40,
              child: ElevatedButton(
                onPressed: creating ? null : onSubmit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: kPrimary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
                child: Text(
                  creating ? 'Creating...' : 'Create User',
                  style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5),
                ),
              ),
            ),

          ],
        ),
      ),
    );
  }
}

// ── Campo de texto ────────────────────────────────────────────────────────────

class _Field extends StatelessWidget {
  const _Field({
    required this.controller,
    required this.label,
    required this.hint,
    this.obscure = false,
  });
  final TextEditingController controller;
  final String label;
  final String hint;
  final bool   obscure;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label.toUpperCase(),
          style: const TextStyle(
              fontSize: 9, letterSpacing: 1.5, color: kMuted, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 6),
        TextField(
          controller:  controller,
          obscureText: obscure,
          style: const TextStyle(color: kForeground, fontSize: 13),
          decoration: InputDecoration(
            hintText: hint,
            isDense: true,
            filled: true,
            fillColor: kSurface2,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: kBorderColor),
            ),
          ),
        ),
      ],
    );
  }
}

// ── Cabecera de columna ───────────────────────────────────────────────────────

class _ColHeader extends StatelessWidget {
  const _ColHeader(this.label, {this.textAlign = TextAlign.start});
  final String    label;
  final TextAlign textAlign;

  @override
  Widget build(BuildContext context) => Text(
    label.toUpperCase(),
    style: const TextStyle(fontSize: 9, letterSpacing: 1.5, color: kMuted),
    textAlign: textAlign,
  );
}

// ── Fila de usuario ───────────────────────────────────────────────────────────

class _UserRow extends StatefulWidget {
  const _UserRow({
    required this.user,
    required this.isSelf,
    required this.onRoleChanged,
    required this.onToggleActive,
    required this.onDelete,
    this.narrow = false,
  });
  final AppUser                    user;
  final bool                       isSelf;
  final void Function(String role) onRoleChanged;
  final VoidCallback               onToggleActive;
  final VoidCallback               onDelete;
  final bool                       narrow;

  @override
  State<_UserRow> createState() => _UserRowState();
}

class _UserRowState extends State<_UserRow> {
  bool _hovered      = false;
  bool _longPressed  = false;

  void _showRoleModal(BuildContext context, String currentRole) {
    showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: kSurfaceColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
        ),
        title: const Text('Change Role',
            style: TextStyle(color: kForeground, fontSize: 15)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: ['user', 'admin'].map((value) {
            final isSelected = currentRole == value;
            return GestureDetector(
              onTap: () {
                Navigator.of(ctx).pop();
                if (!isSelected) widget.onRoleChanged(value);
              },
              child: Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: isSelected
                      ? kPrimary.withValues(alpha: 0.12)
                      : kSurface2,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: isSelected
                        ? kPrimary.withValues(alpha: 0.4)
                        : kBorderColor,
                  ),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        value == 'admin' ? 'Admin' : 'User',
                        style: TextStyle(
                          fontSize: 13,
                          color: isSelected ? kPrimary : kForeground,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                    ),
                    if (isSelected)
                      const Icon(Icons.check, size: 16, color: kPrimary),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final u = widget.user;
    final narrow = widget.narrow;

    final roleLabel = u.role == 'admin' ? 'Admin' : 'User';

    // Ancho fijo para que "User" y "Admin" ocupen exactamente lo mismo
    final roleChip = SizedBox(
      width: 72,
      height: 28,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          color: kSurface2,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: kBorderColor),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                roleLabel,
                style: const TextStyle(color: kForeground, fontSize: 12),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 2),
            const Icon(Icons.arrow_drop_down, size: 14, color: kMuted),
          ],
        ),
      ),
    );

    final lockedChip = SizedBox(
      width: 72,
      height: 28,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          color: kSurface2.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: kBorderColor.withValues(alpha: 0.4)),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                roleLabel,
                style: TextStyle(color: kMuted.withValues(alpha: 0.6), fontSize: 12),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 2),
            Icon(Icons.lock_outline, size: 12, color: kMuted.withValues(alpha: 0.4)),
          ],
        ),
      ),
    );

    // Badge de estado reutilizable (narrow: shrink to content; desktop: stretch)
    final statusBadge = GestureDetector(
      onTap: widget.onToggleActive,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: u.isActive
              ? kStatGreen.withValues(alpha: 0.12)
              : Colors.red.withValues(alpha: 0.10),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: u.isActive
                ? kStatGreen.withValues(alpha: 0.4)
                : Colors.red.withValues(alpha: 0.3),
          ),
        ),
        child: Row(
          mainAxisSize: narrow ? MainAxisSize.min : MainAxisSize.max,
          children: [
            Container(
              width: 6, height: 6,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: u.isActive ? kStatGreen : Colors.redAccent,
              ),
            ),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                u.isActive ? 'Active' : 'Inactive',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: u.isActive ? kStatGreen : Colors.redAccent,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );

    final row = MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit:  (_) => setState(() => _hovered = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        color: _longPressed
            ? Colors.red.withValues(alpha: 0.06)
            : _hovered
                ? kPrimary.withValues(alpha: 0.04)
                : Colors.transparent,
        padding: EdgeInsets.symmetric(horizontal: narrow ? 12 : 20, vertical: 7),
        child: Row(
          children: [
            // Avatar + nombre
            Expanded(
              flex: narrow ? 2 : 1,
              child: Row(
                children: [
                  Container(
                    width: 30, height: 30,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF6B3A9E), Color(0xFF4A2270)],
                      ),
                      shape: BoxShape.circle,
                      border: Border.all(color: kPrimary.withValues(alpha: 0.3)),
                    ),
                    child: Center(
                      child: Text(
                        u.username.isNotEmpty ? u.username[0].toUpperCase() : '?',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: kForeground,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      u.username,
                      style: const TextStyle(fontSize: 13, color: kForeground),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),

            // Email (solo en escritorio)
            if (!narrow)
              Expanded(
                child: Text(
                  u.email,
                  style: const TextStyle(fontSize: 12, color: kMuted),
                  overflow: TextOverflow.ellipsis,
                ),
              ),

            // Rol
            Expanded(
              child: narrow
                  ? Center(
                      child: widget.isSelf
                          ? Tooltip(
                              message: 'You cannot change your own role',
                              child: lockedChip,
                            )
                          : GestureDetector(
                              onTap: () => _showRoleModal(context, u.role),
                              child: roleChip,
                            ),
                    )
                  : Align(
                      alignment: Alignment.centerLeft,
                      child: SizedBox(
                        width: 110,
                        height: 30,
                        child: widget.isSelf
                            ? Tooltip(
                                message: 'You cannot change your own role',
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10),
                                  decoration: BoxDecoration(
                                    color: kSurface2.withValues(alpha: 0.5),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(color: kBorderColor.withValues(alpha: 0.4)),
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        u.role == 'admin' ? 'Admin' : 'User',
                                        style: TextStyle(color: kMuted.withValues(alpha: 0.6), fontSize: 12),
                                      ),
                                      Icon(Icons.lock_outline, size: 13, color: kMuted.withValues(alpha: 0.4)),
                                    ],
                                  ),
                                ),
                              )
                            : PopupMenuButton<String>(
                                initialValue: u.role,
                                onSelected: widget.onRoleChanged,
                                offset: const Offset(0, 32),
                                color: kSurface2,
                                constraints: const BoxConstraints(minWidth: 110, maxWidth: 110),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
                                ),
                                itemBuilder: (_) => const [
                                  PopupMenuItem(value: 'user',  child: Text('User',  style: TextStyle(color: kForeground, fontSize: 12))),
                                  PopupMenuItem(value: 'admin', child: Text('Admin', style: TextStyle(color: kForeground, fontSize: 12))),
                                ],
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10),
                                  decoration: BoxDecoration(
                                    color: kSurface2,
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(color: kBorderColor),
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        u.role == 'admin' ? 'Admin' : 'User',
                                        style: const TextStyle(color: kForeground, fontSize: 12),
                                      ),
                                      const Icon(Icons.arrow_drop_down, size: 16, color: kMuted),
                                    ],
                                  ),
                                ),
                              ),
                      ),
                    ),
            ),

            // Estado activo/inactivo
            Expanded(
              child: narrow
                  ? Align(
                      alignment: Alignment.centerRight,
                      child: statusBadge,
                    )
                  : MouseRegion(
                      cursor: SystemMouseCursors.click,
                      child: statusBadge,
                    ),
            ),

            if (!narrow) ...[
              const SizedBox(width: 12),
              AnimatedOpacity(
                opacity: _hovered ? 1.0 : 0.0,
                duration: const Duration(milliseconds: 150),
                child: IconButton(
                  icon: const Icon(Icons.delete_outline, size: 16),
                  color: kMuted,
                  hoverColor: Colors.red.withValues(alpha: 0.1),
                  tooltip: 'Delete user',
                  onPressed: widget.onDelete,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                ),
              ),
            ],
          ],
        ),
      ),
    );

    if (!narrow) return row;

    return GestureDetector(
      onLongPress: () async {
        setState(() => _longPressed = true);
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            backgroundColor: kSurfaceColor,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
            ),
            title: const Text('Delete user',
                style: TextStyle(color: kForeground, fontSize: 15)),
            content: Text(
              'Delete "${u.username}"? All their players and snapshots will also be removed.',
              style: const TextStyle(color: kMuted, fontSize: 13),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: const Text('Cancel', style: TextStyle(color: kMuted)),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                child: const Text('Delete',
                    style: TextStyle(color: Colors.redAccent)),
              ),
            ],
          ),
        );
        if (!mounted) return;
        setState(() => _longPressed = false);
        if (confirmed == true) widget.onDelete();
      },
      child: row,
    );
  }
}

// ── Modal "New User" para móvil ───────────────────────────────────────────────

class _NewUserMobileDialog extends ConsumerStatefulWidget {
  const _NewUserMobileDialog();

  @override
  ConsumerState<_NewUserMobileDialog> createState() =>
      _NewUserMobileDialogState();
}

class _NewUserMobileDialogState extends ConsumerState<_NewUserMobileDialog> {
  final _emailCtrl    = TextEditingController();
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  String  _role     = 'user';
  bool    _creating = false;
  String? _error;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_emailCtrl.text.trim().isEmpty ||
        _usernameCtrl.text.trim().isEmpty ||
        _passwordCtrl.text.isEmpty) {
      setState(() => _error = 'All fields are required.');
      return;
    }
    if (_passwordCtrl.text.length < 6) {
      setState(() => _error = 'Password must be at least 6 characters.');
      return;
    }
    setState(() { _creating = true; _error = null; });
    final err = await ref.read(adminUsersProvider.notifier).createUser(
      email:    _emailCtrl.text.trim(),
      username: _usernameCtrl.text.trim(),
      password: _passwordCtrl.text,
      role:     _role,
    );
    if (!mounted) return;
    if (err != null) {
      setState(() { _creating = false; _error = err; });
    } else {
      Navigator.of(context).pop(true);
    }
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required String hint,
    bool obscure = false,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label.toUpperCase(),
            style: const TextStyle(color: kMuted, fontSize: 10, letterSpacing: 1.2)),
        const SizedBox(height: 4),
        TextField(
          controller:  controller,
          obscureText: obscure,
          style: const TextStyle(color: kForeground, fontSize: 13),
          decoration: InputDecoration(
            hintText: hint,
            isDense: true,
            filled: true,
            fillColor: kSurface2,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: kBorderColor),
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: kSurfaceColor,
      insetPadding:
          const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Título estilo AddPlayerDialog
              const Text(
                'NEW USER',
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

              // Campos
              _field(controller: _emailCtrl,    label: 'Email',    hint: 'user@example.com'),
              const SizedBox(height: 12),
              _field(controller: _usernameCtrl, label: 'Username', hint: 'username'),
              const SizedBox(height: 12),
              _field(controller: _passwordCtrl, label: 'Password', hint: '••••••••', obscure: true),
              const SizedBox(height: 12),

              // Selector de rol
              const Text('ROLE',
                  style: TextStyle(color: kMuted, fontSize: 10, letterSpacing: 1.2)),
              const SizedBox(height: 8),
              Row(
                children: ['user', 'admin'].map((v) {
                  final selected = _role == v;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _role = v),
                      child: Container(
                        margin: EdgeInsets.only(right: v == 'user' ? 6 : 0),
                        padding: const EdgeInsets.symmetric(vertical: 10),
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
                        child: Center(
                          child: Text(
                            v == 'admin' ? 'Admin' : 'User',
                            style: TextStyle(
                              fontSize: 13,
                              color: selected ? kPrimaryLight : kMuted,
                              fontWeight: selected
                                  ? FontWeight.w600
                                  : FontWeight.normal,
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),

              // Error
              if (_error != null) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
                  ),
                  child: Text(_error!,
                      style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
                ),
                const SizedBox(height: 16),
              ],

              // Botones
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _creating ? null : () => Navigator.of(context).pop(),
                    child: const Text('Cancel',
                        style: TextStyle(color: kMuted)),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _creating ? null : _submit,
                    child: _creating
                        ? const SizedBox(
                            width: 16, height: 16,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('CREATE USER',
                            style: TextStyle(letterSpacing: 1.5, fontSize: 12)),
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
