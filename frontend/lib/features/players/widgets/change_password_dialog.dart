import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';
import '../../../core/auth/auth_provider.dart';
import '../../../core/theme/app_theme.dart';

class ChangePasswordDialog extends ConsumerStatefulWidget {
  const ChangePasswordDialog({super.key});

  @override
  ConsumerState<ChangePasswordDialog> createState() => _ChangePasswordDialogState();
}

class _ChangePasswordDialogState extends ConsumerState<ChangePasswordDialog> {
  final _currentCtrl = TextEditingController();
  final _newCtrl     = TextEditingController();
  final _confirmCtrl = TextEditingController();

  bool    _loading  = false;
  String? _error;
  bool    _success  = false;

  @override
  void dispose() {
    _currentCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final current = _currentCtrl.text;
    final newPwd  = _newCtrl.text;
    final confirm = _confirmCtrl.text;

    if (current.isEmpty || newPwd.isEmpty || confirm.isEmpty) {
      setState(() => _error = 'Please fill in all fields.');
      return;
    }
    if (newPwd.length < 6) {
      setState(() => _error = 'New password must be at least 6 characters.');
      return;
    }
    if (newPwd != confirm) {
      setState(() => _error = 'Passwords do not match.');
      return;
    }
    if (newPwd == current) {
      setState(() => _error = 'New password must be different from the current one.');
      return;
    }

    setState(() { _loading = true; _error = null; });

    try {
      await ref.read(authRepositoryProvider).changePassword(current, newPwd);
      if (mounted) setState(() { _loading = false; _success = true; });
    } on DioException catch (e) {
      if (mounted) setState(() { _loading = false; _error = e.userMessage; });
    } catch (_) {
      if (mounted) setState(() { _loading = false; _error = 'An unexpected error occurred.'; });
    }
  }

  @override
  Widget build(BuildContext context) {
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
          child: _success
              ? _SuccessView(onClose: () => Navigator.of(context).pop())
              : _FormView(
                  currentCtrl: _currentCtrl,
                  newCtrl:     _newCtrl,
                  confirmCtrl: _confirmCtrl,
                  loading:     _loading,
                  error:       _error,
                  onSubmit:    _submit,
                  onCancel:    () => Navigator.of(context).pop(),
                ),
        ),
      ),
    );
  }
}

// ── Vistas internas ───────────────────────────────────────────────────────────

class _FormView extends StatelessWidget {
  const _FormView({
    required this.currentCtrl,
    required this.newCtrl,
    required this.confirmCtrl,
    required this.loading,
    required this.error,
    required this.onSubmit,
    required this.onCancel,
  });

  final TextEditingController currentCtrl;
  final TextEditingController newCtrl;
  final TextEditingController confirmCtrl;
  final bool    loading;
  final String? error;
  final VoidCallback onSubmit;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          'Change password',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: kForeground),
        ),
        const SizedBox(height: 20),
        _PwdField(controller: currentCtrl, label: 'Current password', hint: '••••••••'),
        const SizedBox(height: 12),
        _PwdField(controller: newCtrl,     label: 'New password',     hint: '••••••••'),
        const SizedBox(height: 12),
        _PwdField(controller: confirmCtrl, label: 'Confirm password', hint: '••••••••',
          onSubmitted: (_) => onSubmit()),
        if (error != null) ...[
          const SizedBox(height: 12),
          Text(error!, style: const TextStyle(fontSize: 12, color: Colors.redAccent)),
        ],
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: loading ? null : onCancel,
                child: const Text('Cancel'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: ElevatedButton(
                onPressed: loading ? null : onSubmit,
                child: Text(loading ? 'Saving...' : 'Save'),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _SuccessView extends StatelessWidget {
  const _SuccessView({required this.onClose});
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Image.asset('assets/icons/okey_dokey.png', width: 100, height: 100),
        const SizedBox(height: 16),
        const Text(
          'Password updated',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: kForeground),
        ),
        const SizedBox(height: 8),
        const Text(
          'Your password has been changed successfully.',
          style: TextStyle(fontSize: 13, color: kMuted),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(onPressed: onClose, child: const Text('Close')),
        ),
      ],
    );
  }
}

class _PwdField extends StatelessWidget {
  const _PwdField({
    required this.controller,
    required this.label,
    required this.hint,
    this.onSubmitted,
  });

  final TextEditingController controller;
  final String label;
  final String hint;
  final void Function(String)? onSubmitted;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label.toUpperCase(),
          style: const TextStyle(fontSize: 9, letterSpacing: 1.5, color: kMuted, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 6),
        TextField(
          controller:  controller,
          obscureText: true,
          onSubmitted: onSubmitted,
          style: const TextStyle(color: kForeground, fontSize: 13),
          decoration: InputDecoration(
            hintText: hint,
            isDense: true,
            filled: true,
            fillColor: kSurface2,
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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
