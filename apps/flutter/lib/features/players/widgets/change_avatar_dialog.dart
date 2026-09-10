import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../../core/auth/auth_provider.dart';
import '../../../core/theme/app_theme.dart';

class ChangeAvatarDialog extends ConsumerStatefulWidget {
  const ChangeAvatarDialog({super.key});

  @override
  ConsumerState<ChangeAvatarDialog> createState() => _ChangeAvatarDialogState();
}

class _ChangeAvatarDialogState extends ConsumerState<ChangeAvatarDialog> {
  bool    _loading = false;
  String? _error;

  Future<void> _pick(ImageSource source) async {
    final picker = ImagePicker();
    final XFile? img = await picker.pickImage(
      source:       source,
      imageQuality: 80,
      maxWidth:     512,
    );
    if (img == null) return;

    setState(() { _loading = true; _error = null; });
    try {
      final bytes = await img.readAsBytes();
      await ref.read(authProvider.notifier).uploadAvatar(bytes, img.name);
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = 'Upload failed. Try again.'; });
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
        constraints: const BoxConstraints(maxWidth: 320),
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Change photo',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: kForeground),
              ),
              const SizedBox(height: 20),
              if (_loading)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Center(child: CircularProgressIndicator()),
                )
              else ...[
                _SourceButton(
                  icon:  Icons.photo_library_outlined,
                  label: 'Choose from gallery',
                  onTap: () => _pick(ImageSource.gallery),
                ),
                const SizedBox(height: 10),
                _SourceButton(
                  icon:  Icons.camera_alt_outlined,
                  label: 'Take a photo',
                  onTap: () => _pick(ImageSource.camera),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(fontSize: 12, color: Colors.redAccent)),
              ],
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: _loading ? null : () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SourceButton extends StatelessWidget {
  const _SourceButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData     icon;
  final String       label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: kSurface2,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: kBorderColor),
        ),
        child: Row(
          children: [
            Icon(icon, size: 18, color: kPrimaryLight),
            const SizedBox(width: 12),
            Text(label, style: const TextStyle(color: kForeground, fontSize: 14)),
          ],
        ),
      ),
    );
  }
}
