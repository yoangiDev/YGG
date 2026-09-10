import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme/app_theme.dart';
import '../core/auth/auth_provider.dart';
import '../features/auth/widgets/login_branding_panel.dart';
import '../features/auth/widgets/login_form_panel.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _userCtrl = TextEditingController();
  final _pass2Ctrl = TextEditingController();

  bool _isRegister = false;
  bool _obscurePass = true;
  bool _loading = false;

  late final AnimationController _glowCtrl;
  late final Animation<double> _glowAnim;

  void _clearError() {
    if (ref.read(authProvider).errorMessage != null) {
      ref.read(authProvider.notifier).clearError();
    }
  }

  @override
  void initState() {
    super.initState();
    _glowCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3200),
    )..repeat(reverse: true);
    _glowAnim = CurvedAnimation(parent: _glowCtrl, curve: Curves.easeInOut);

    for (final ctrl in [_emailCtrl, _passCtrl, _userCtrl, _pass2Ctrl]) {
      ctrl.addListener(_clearError);
    }
  }

  @override
  void dispose() {
    _glowCtrl.dispose();
    for (final ctrl in [_emailCtrl, _passCtrl, _userCtrl, _pass2Ctrl]) {
      ctrl.removeListener(_clearError);
      ctrl.dispose();
    }
    super.dispose();
  }

  LoginFormPanel _buildFormPanel(String? error) => LoginFormPanel(
    formKey: _formKey,
    emailCtrl: _emailCtrl,
    passCtrl: _passCtrl,
    userCtrl: _userCtrl,
    pass2Ctrl: _pass2Ctrl,
    isRegister: _isRegister,
    obscurePass: _obscurePass,
    loading: _loading,
    error: error,
    onToggleObscure: () => setState(() => _obscurePass = !_obscurePass),
    onToggleMode: () {
      setState(() {
        _isRegister = !_isRegister;
        _obscurePass = true;
        _formKey.currentState?.reset();
        _userCtrl.clear();
        _pass2Ctrl.clear();
      });
      ref.read(authProvider.notifier).clearError();
    },
    onSubmit: _submit,
  );

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);

    final notifier = ref.read(authProvider.notifier);
    final ok = _isRegister
        ? await notifier.register(
            _emailCtrl.text.trim(),
            _userCtrl.text.trim(),
            _passCtrl.text,
          )
        : await notifier.login(_emailCtrl.text.trim(), _passCtrl.text);

    if (mounted && !ok) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final error = ref.watch(authProvider).errorMessage;

    return Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) {
          final formPanel = _buildFormPanel(error);
          if (constraints.maxWidth < 600) return formPanel;
          return Row(
            children: [
              Expanded(flex: 55, child: LoginBrandingPanel(glowAnim: _glowAnim)),
              Container(
                width: 1,
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [Colors.transparent, kPrimaryDim, Colors.transparent],
                    stops: [0.0, 0.5, 1.0],
                  ),
                ),
              ),
              Expanded(flex: 45, child: _buildFormPanel(error)),
            ],
          );
        },
      ),
    );
  }
}
