import 'dart:async';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/auth/auth_provider.dart';
import '../../../screens/admin_screen.dart';
import '../providers/players_provider.dart';
import '../providers/snapshot_provider.dart';
import 'change_avatar_dialog.dart';
import 'change_password_dialog.dart';
import 'package:flutter_svg/flutter_svg.dart';

class HextechHeader extends ConsumerWidget {
  const HextechHeader({super.key, this.showAdminLink = true, this.title, this.showBackButton});

  /// Poner a false en AdminScreen para no mostrar el acceso al panel desde dentro del propio panel.
  final bool showAdminLink;
  final String? title;
  /// null = auto (usa canPop). false = nunca muestra el back button.
  final bool? showBackButton;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth              = ref.watch(authProvider);
    final activePlayerIds   = ref.watch(snapshotActivePlayerIdsProvider);
    final mq                = MediaQuery.of(context);
    final narrow  = mq.size.width < 600;
    final topPad  = narrow ? mq.padding.top : 0.0;
    final canPop  = narrow && (showBackButton ?? Navigator.of(context).canPop());

    // Gradiente móvil: pico en la posición del logo.
    // Sin back button → logo en el borde izquierdo (stop 0).
    // Con back button → logo a ~22% (después de flecha + divisor).
    final mobileGradient = canPop
        ? const LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: [Colors.transparent, Color(0xFF2D1155), Colors.transparent],
            stops: [0.0, 0.22, 0.70],
          )
        : const LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: [Color(0xFF2D1155), Colors.transparent],
          );

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // ── Barra principal ────────────────────────────────────────────────
        Container(
          padding: EdgeInsets.fromLTRB(
            narrow ? 14 : 24,
            (narrow ? 8 : 10) + topPad,
            narrow ? 14 : 24,
            narrow ? 8 : 10,
          ),
          decoration: BoxDecoration(
            gradient: narrow
                ? mobileGradient
                // Escritorio: pico centrado donde está el logo
                : const LinearGradient(
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                    colors: [
                      Colors.transparent,
                      Color(0xFF2D1155),
                      Colors.transparent,
                    ],
                    stops: [0.25, 0.5, 0.75],
                  ),
          ),
          child: narrow
              // ── Layout móvil ─────────────────────────────────────────────
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    // Izquierda: botón volver si hay ruta previa, logo si no
                    if (canPop)
                      IconButton(
                        icon: const Icon(Icons.arrow_back_ios_new, size: 16, color: kMuted),
                        onPressed: () => Navigator.of(context).pop(),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                      )
                    else
                      SvgPicture.asset('assets/logo/logo.svg', width: 43, height: 32),
                    if (title != null) ...[
                      // Con back button: [|] [logo] [título]
                      if (canPop) ...[
                        const SizedBox(width: 6),
                        Container(width: 1, height: 24, color: kPrimary.withValues(alpha: 0.25)),
                        const SizedBox(width: 8),
                        SvgPicture.asset('assets/logo/logo.svg', width: 43, height: 32),
                        const SizedBox(width: 10),
                      ]
                      // Sin back button: [logo ya está] [|] [título]
                      else ...[
                        const SizedBox(width: 10),
                        Container(width: 1, height: 24, color: kPrimary.withValues(alpha: 0.25)),
                        const SizedBox(width: 10),
                      ],
                      Text(
                        title!,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: kForeground,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ],
                    const Spacer(),
                    if (activePlayerIds.isNotEmpty) ...[
                      _SnapshotActivityIcon(playerIds: activePlayerIds),
                      const SizedBox(width: 4),
                    ],
                    _UserMenu(username: auth.username, avatarUrl: auth.avatarUrl, showAdminLink: showAdminLink, narrow: true),
                  ],
                )
              // ── Layout escritorio: Stack con logo centrado ───────────────
              : Stack(
                  alignment: Alignment.center,
                  children: [
                    // Logo centrado con líneas decorativas
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 72, height: 1,
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [Colors.transparent, kPrimary.withValues(alpha: 0.6)],
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        SvgPicture.asset('assets/logo/logo.svg', width: 70, height: 52),
                        const SizedBox(width: 12),
                        Container(
                          width: 72, height: 1,
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [kPrimary.withValues(alpha: 0.6), Colors.transparent],
                            ),
                          ),
                        ),
                      ],
                    ),
                    // Texto izquierda + usuario derecha
                    Row(
                      children: [
                        if (title != null)
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const _LiveClock(),
                              const SizedBox(height: 2),
                              Text(
                                title!,
                                style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                  color: kForeground,
                                  letterSpacing: 0.3,
                                ),
                              ),
                            ],
                          ),
                        const Spacer(),
                        if (activePlayerIds.isNotEmpty) ...[
                          _SnapshotActivityIcon(playerIds: activePlayerIds),
                          const SizedBox(width: 8),
                        ],
                        _UserMenu(username: auth.username, avatarUrl: auth.avatarUrl, showAdminLink: showAdminLink),
                      ],
                    ),
                  ],
                ),
        ),

        // ── Separador luminoso ─────────────────────────────────────────────
        Container(
          height: 1,
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [
              Colors.transparent,
              kPrimary.withValues(alpha: 0.45),
              kPrimaryDim.withValues(alpha: 0.6),
              kPrimary.withValues(alpha: 0.45),
              Colors.transparent,
            ]),
          ),
        ),
      ],
    );
  }
}

// ── Menú de usuario ──────────────────────────────────────────────────────────

class _UserMenu extends ConsumerStatefulWidget {
  const _UserMenu({this.username, this.avatarUrl, required this.showAdminLink, this.narrow = false});
  final String? username;
  final String? avatarUrl;
  final bool    showAdminLink;
  final bool    narrow;

  @override
  ConsumerState<_UserMenu> createState() => _UserMenuState();
}

class _UserMenuState extends ConsumerState<_UserMenu> {
  bool _isHovered = false;
  final _triggerKey = GlobalKey();
  double _triggerWidth = 180;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _measureTrigger());
  }

  void _measureTrigger() {
    final box = _triggerKey.currentContext?.findRenderObject() as RenderBox?;
    if (box != null && mounted) setState(() => _triggerWidth = box.size.width);
  }

  void _showProfile(BuildContext context) {
    showDialog<void>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.6),
      builder: (_) => const _ProfileDialog(),
    );
  }

  // ── Modal centrado para móvil ─────────────────────────────────────────────
  void _showMobileModal(BuildContext context, bool isAdmin) {
    final auth = ref.read(authProvider);
    showDialog<void>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.6),
      builder: (dialogCtx) => _MobileUserModal(
        username:      auth.username,
        email:         auth.email,
        avatarUrl:     auth.avatarUrl,
        isAdmin:       isAdmin,
        showAdminLink: widget.showAdminLink,
        onProfileTap: () {
          Navigator.of(dialogCtx).pop();
          showDialog<void>(
            context: context,
            barrierColor: Colors.black.withValues(alpha: 0.6),
            builder: (_) => const _ProfileDialog(),
          );
        },
        onAdminTap: () {
          Navigator.of(dialogCtx).pop();
          Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const AdminScreen()),
          );
        },
        onLogoutTap: () async {
          Navigator.of(dialogCtx).pop();
          final confirmed = await showDialog<bool>(
            context: context,
            builder: (_) => AlertDialog(
              backgroundColor: kSurfaceColor,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
              ),
              title: const Text('Log out', style: TextStyle(color: kForeground, fontSize: 15)),
              content: const Text('Are you sure you want to log out?', style: TextStyle(color: kMuted, fontSize: 13)),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('Cancel', style: TextStyle(color: kMuted)),
                ),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Log out', style: TextStyle(color: Colors.redAccent)),
                ),
              ],
            ),
          );
          if (confirmed == true) ref.read(authProvider.notifier).logout();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isAdmin = ref.watch(authProvider).isAdmin;

    // ── Móvil: avatar que abre dialog centrado ────────────────────────────
    if (widget.narrow) {
      return GestureDetector(
        onTap: () => _showMobileModal(context, isAdmin),
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: _UserAvatar(username: widget.username, avatarUrl: widget.avatarUrl, size: 32, fontSize: 11),
        ),
      );
    }

    // ── Escritorio: dropdown MenuAnchor (sin cambios) ─────────────────────
    return MenuAnchor(
      alignmentOffset: const Offset(0, 6),
      style: MenuStyle(
        minimumSize: WidgetStatePropertyAll(Size(_triggerWidth, 0)),
        maximumSize: WidgetStatePropertyAll(Size(_triggerWidth, double.infinity)),
        backgroundColor: const WidgetStatePropertyAll(kSurfaceColor),
        elevation: const WidgetStatePropertyAll(12),
        shadowColor: WidgetStatePropertyAll(Colors.black.withValues(alpha: 0.5)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
            side: BorderSide(color: kPrimary.withValues(alpha: 0.3)),
          ),
        ),
        padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(vertical: 6)),
      ),
      menuChildren: [
        MenuItemButton(
          style: ButtonStyle(
            mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
            padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 16, vertical: 10)),
          ),
          leadingIcon: const Icon(Icons.person_outline, size: 16, color: kPrimaryLight),
          onPressed: () => _showProfile(context),
          child: const Text('Profile', style: TextStyle(color: kForeground, fontSize: 13)),
        ),
        if (widget.showAdminLink && isAdmin) ...[
          const Divider(height: 1, thickness: 1, color: kBorderColor),
          MenuItemButton(
            style: ButtonStyle(
              mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
              padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 16, vertical: 10)),
            ),
            leadingIcon: const Icon(Icons.shield_outlined, size: 16, color: kPrimaryLight),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const AdminScreen()),
            ),
            child: const Text('Admin Panel', style: TextStyle(color: kForeground, fontSize: 13)),
          ),
        ],
        const Divider(height: 1, thickness: 1, color: kBorderColor),
        MenuItemButton(
          style: ButtonStyle(
            mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
            padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 16, vertical: 10)),
          ),
          leadingIcon: const Icon(Icons.logout, size: 16, color: Colors.redAccent),
          onPressed: () async {
            final confirmed = await showDialog<bool>(
              context: context,
              builder: (_) => AlertDialog(
                backgroundColor: kSurfaceColor,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
                ),
                title: const Text('Log out', style: TextStyle(color: kForeground, fontSize: 15)),
                content: const Text('Are you sure you want to log out?', style: TextStyle(color: kMuted, fontSize: 13)),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    child: const Text('Cancel', style: TextStyle(color: kMuted)),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    child: const Text('Log out', style: TextStyle(color: Colors.redAccent)),
                  ),
                ],
              ),
            );
            if (confirmed == true) ref.read(authProvider.notifier).logout();
          },
          child: const Text('Log out', style: TextStyle(color: Colors.redAccent, fontSize: 13)),
        ),
      ],
      builder: (context, controller, _) => MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _isHovered = true),
        onExit:  (_) => setState(() => _isHovered = false),
        child: InkWell(
          onTap: () => controller.isOpen ? controller.close() : controller.open(),
          borderRadius: BorderRadius.circular(6),
          hoverColor: Colors.transparent,
          child: AnimatedContainer(
            key: _triggerKey,
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: _isHovered ? kPrimary.withValues(alpha: 0.5) : Colors.transparent,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _UserAvatar(username: widget.username, avatarUrl: widget.avatarUrl, size: 28, fontSize: 9),
                const SizedBox(width: 10),
                Text(
                  widget.username ?? 'Summoner',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kForeground),
                ),
                const SizedBox(width: 8),
                AnimatedRotation(
                  turns: controller.isOpen ? 0.5 : 0,
                  duration: const Duration(milliseconds: 150),
                  child: const Icon(Icons.keyboard_arrow_down, size: 18, color: kMuted),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Modal de usuario para móvil ───────────────────────────────────────────────

class _MobileUserModal extends StatelessWidget {
  const _MobileUserModal({
    required this.username,
    required this.email,
    this.avatarUrl,
    required this.isAdmin,
    required this.showAdminLink,
    required this.onProfileTap,
    required this.onAdminTap,
    required this.onLogoutTap,
  });

  final String?      username;
  final String?      email;
  final String?      avatarUrl;
  final bool         isAdmin;
  final bool         showAdminLink;
  final VoidCallback onProfileTap;
  final VoidCallback onAdminTap;
  final VoidCallback onLogoutTap;

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: kSurfaceColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 340),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _UserAvatar(username: username, avatarUrl: avatarUrl, size: 72),
              const SizedBox(height: 12),
              Text(
                username ?? 'Summoner',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: kForeground,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 20),
              Container(
                height: 1,
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [
                    Colors.transparent,
                    kPrimary.withValues(alpha: 0.4),
                    Colors.transparent,
                  ]),
                ),
              ),
              const SizedBox(height: 8),
              _ModalOption(
                icon:  Icons.person_outline,
                label: 'Profile',
                onTap: onProfileTap,
              ),
              if (showAdminLink && isAdmin) ...[
                _ModalOption(
                  icon:  Icons.shield_outlined,
                  label: 'Admin Panel',
                  onTap: onAdminTap,
                ),
              ],
              Container(
                height: 1,
                color: kBorderColor.withValues(alpha: 0.4),
              ),
              _ModalOption(
                icon:          Icons.logout,
                label:         'Log out',
                onTap:         onLogoutTap,
                isDestructive: true,
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ModalOption extends StatelessWidget {
  const _ModalOption({
    required this.icon,
    required this.label,
    required this.onTap,
    this.isDestructive = false,
  });

  final IconData     icon;
  final String       label;
  final VoidCallback onTap;
  final bool         isDestructive;

  @override
  Widget build(BuildContext context) {
    final color     = isDestructive ? Colors.redAccent : kForeground;
    final iconColor = isDestructive ? Colors.redAccent : kPrimaryLight;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 13),
        child: Row(
          children: [
            Icon(icon, size: 18, color: iconColor),
            const SizedBox(width: 14),
            Text(label, style: TextStyle(fontSize: 14, color: color)),
          ],
        ),
      ),
    );
  }
}

// ── Diálogo de perfil ─────────────────────────────────────────────────────────

class _ProfileDialog extends ConsumerWidget {
  const _ProfileDialog();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);

    return Dialog(
      backgroundColor: kSurfaceColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 360),
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Avatar grande con botón de edición
              GestureDetector(
                onTap: () => showDialog<void>(
                  context: context,
                  barrierColor: Colors.black.withValues(alpha: 0.6),
                  builder: (_) => const ChangeAvatarDialog(),
                ),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    _UserAvatar(username: auth.username, avatarUrl: auth.avatarUrl, size: 72),
                    Positioned(
                      bottom: 0,
                      right: 0,
                      child: Container(
                        width: 22,
                        height: 22,
                        decoration: BoxDecoration(
                          color: kPrimary,
                          shape: BoxShape.circle,
                          border: Border.all(color: kSurfaceColor, width: 1.5),
                        ),
                        child: const Icon(Icons.edit, size: 12, color: Colors.white),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Username
              Text(
                auth.username ?? 'Summoner',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: kForeground,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 24),

              // Separador
              Container(
                height: 1,
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [
                    Colors.transparent,
                    kPrimary.withValues(alpha: 0.4),
                    Colors.transparent,
                  ]),
                ),
              ),
              const SizedBox(height: 20),

              // Datos
              _InfoRow(icon: Icons.person_outline, label: 'Username', value: auth.username ?? '—'),
              const SizedBox(height: 12),
              _InfoRow(icon: Icons.email_outlined,  label: 'Email',   value: auth.email    ?? '—'),
              const SizedBox(height: 24),

              // Cambiar foto
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.photo_camera_outlined, size: 15),
                  label: const Text('Change photo'),
                  onPressed: () => showDialog<void>(
                    context: context,
                    barrierColor: Colors.black.withValues(alpha: 0.6),
                    builder: (_) => const ChangeAvatarDialog(),
                  ),
                ),
              ),
              const SizedBox(height: 10),

              // Cambiar contraseña
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.key_outlined, size: 15),
                  label: const Text('Change password'),
                  onPressed: () {
                    Navigator.of(context).pop();
                    showDialog<void>(
                      context: context,
                      barrierColor: Colors.black.withValues(alpha: 0.6),
                      builder: (_) => const ChangePasswordDialog(),
                    );
                  },
                ),
              ),
              const SizedBox(height: 10),

              // Cerrar
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String   label;
  final String   value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: kPrimary),
        const SizedBox(width: 10),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label.toUpperCase(),
                style: const TextStyle(fontSize: 9, color: kMuted, letterSpacing: 1.2)),
            Text(value,
                style: const TextStyle(fontSize: 13, color: kForeground, fontWeight: FontWeight.w500)),
          ],
        ),
      ],
    );
  }
}

// ── Avatar de usuario ─────────────────────────────────────────────────────────

class _UserAvatar extends StatelessWidget {
  const _UserAvatar({required this.username, required this.size, this.fontSize, this.avatarUrl});
  final String? username;
  final double  size;
  final double? fontSize;
  final String? avatarUrl;

  @override
  Widget build(BuildContext context) {
    final large   = size > 50;
    final initial = (username?.isNotEmpty == true ? username![0] : 'U').toUpperCase();

    final decoration = BoxDecoration(
      shape: BoxShape.circle,
      border: Border.all(
        color: kPrimary.withValues(alpha: large ? 0.5 : 0.4),
        width: large ? 2.0 : 1.0,
      ),
      boxShadow: large
          ? [BoxShadow(color: kPrimary.withValues(alpha: 0.3), blurRadius: 20)]
          : null,
    );

    if (avatarUrl != null) {
      return Container(
        width: size, height: size,
        decoration: decoration,
        child: ClipOval(
          child: CachedNetworkImage(
            imageUrl: avatarUrl!,
            width: size, height: size,
            fit: BoxFit.cover,
            placeholder: (context2, url) => _InitialCircle(initial: initial, size: size, fontSize: fontSize),
            errorWidget: (context2, url, err) => _InitialCircle(initial: initial, size: size, fontSize: fontSize),
          ),
        ),
      );
    }

    return Container(
      width: size, height: size,
      decoration: decoration.copyWith(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF6B3A9E), Color(0xFF4A2270)],
        ),
      ),
      child: Center(
        child: _InitialCircle(initial: initial, size: size, fontSize: fontSize),
      ),
    );
  }
}

class _InitialCircle extends StatelessWidget {
  const _InitialCircle({required this.initial, required this.size, this.fontSize});
  final String  initial;
  final double  size;
  final double? fontSize;

  @override
  Widget build(BuildContext context) => Text(
    initial,
    style: TextStyle(
      fontSize:   fontSize ?? size * 0.4,
      fontWeight: FontWeight.bold,
      color:      kForeground,
    ),
  );
}

// ── Icono de snapshot en progreso ─────────────────────────────────────────────

class _SnapshotActivityIcon extends ConsumerStatefulWidget {
  const _SnapshotActivityIcon({required this.playerIds});
  final Set<int> playerIds;

  @override
  ConsumerState<_SnapshotActivityIcon> createState() => _SnapshotActivityIconState();
}

class _SnapshotActivityIconState extends ConsumerState<_SnapshotActivityIcon>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => showDialog<void>(
        context: context,
        barrierColor: Colors.black.withValues(alpha: 0.6),
        builder: (_) => _SnapshotProgressModal(playerIds: widget.playerIds),
      ),
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            const Icon(Icons.query_stats_rounded, size: 22, color: kPrimaryLight),
            Positioned(
              top: -2,
              right: -2,
              child: AnimatedBuilder(
                animation: _pulse,
                builder: (_, _) => Opacity(
                  opacity: 0.4 + _pulse.value * 0.6,
                  child: Container(
                    width: 7,
                    height: 7,
                    decoration: const BoxDecoration(
                      color: kStatGreen,
                      shape: BoxShape.circle,
                    ),
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

// ── Modal de progreso de snapshots ────────────────────────────────────────────

class _SnapshotProgressModal extends ConsumerWidget {
  const _SnapshotProgressModal({required this.playerIds});
  final Set<int> playerIds;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final players = ref.watch(playersProvider).valueOrNull ?? [];
    // Relee los ids activos en tiempo real por si termina alguno mientras el modal está abierto
    final activeIds = ref.watch(snapshotActivePlayerIdsProvider);
    final ids = activeIds.isEmpty ? playerIds : activeIds;

    return Dialog(
      backgroundColor: kSurfaceColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: kPrimary.withValues(alpha: 0.2)),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 340),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.query_stats_rounded, size: 16, color: kPrimaryLight),
                  const SizedBox(width: 8),
                  Text(
                    ids.length > 1 ? 'SNAPSHOTS IN PROGRESS' : 'SNAPSHOT IN PROGRESS',
                    style: const TextStyle(
                      fontSize: 10,
                      letterSpacing: 1.4,
                      color: kMuted,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ...ids.map((playerId) {
                final player = players.where((p) => p.id == playerId).firstOrNull;
                final name   = player != null
                    ? (player.nickname.isNotEmpty ? player.nickname : player.gameName)
                    : 'Player #$playerId';
                return _SnapshotJobRow(playerId: playerId, name: name);
              }),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SnapshotJobRow extends ConsumerWidget {
  const _SnapshotJobRow({required this.playerId, required this.name});
  final int    playerId;
  final String name;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final progress = ref.watch(snapshotCreationProgressProvider(playerId));

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            name,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: kForeground),
          ),
          const SizedBox(height: 8),
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: (progress / 100).clamp(0.0, 1.0)),
            duration: const Duration(milliseconds: 600),
            curve: Curves.easeOut,
            builder: (_, value, _) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(99),
                  child: Container(
                    width: double.infinity,
                    height: 8,
                    color: kSurface2,
                    child: FractionallySizedBox(
                      alignment: Alignment.centerLeft,
                      widthFactor: value,
                      child: Container(
                        decoration: const BoxDecoration(
                          borderRadius: BorderRadius.all(Radius.circular(99)),
                          gradient: LinearGradient(
                            colors: [kPrimaryDim, kPrimary, kPrimaryLight],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${(value * 100).round()}%',
                  style: const TextStyle(fontSize: 11, color: kPrimaryLight, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Reloj en tiempo real ──────────────────────────────────────────────────────

class _LiveClock extends StatefulWidget {
  const _LiveClock();

  @override
  State<_LiveClock> createState() => _LiveClockState();
}

class _LiveClockState extends State<_LiveClock> {
  late String _time;
  late Timer _timer;

  String _format(DateTime dt) =>
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';

  @override
  void initState() {
    super.initState();
    _time = _format(DateTime.now());
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _time = _format(DateTime.now()));
    });
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Text(
      _time,
      style: TextStyle(
        fontSize: 9,
        letterSpacing: 2.5,
        color: kMuted,
      ),
    );
  }
}
