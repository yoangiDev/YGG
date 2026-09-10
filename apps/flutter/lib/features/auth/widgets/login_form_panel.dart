import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../../core/theme/app_theme.dart';

class LoginFormPanel extends StatelessWidget {
  const LoginFormPanel({
    super.key,
    required this.formKey,
    required this.emailCtrl,
    required this.passCtrl,
    required this.userCtrl,
    required this.pass2Ctrl,
    required this.isRegister,
    required this.obscurePass,
    required this.loading,
    required this.error,
    required this.onToggleObscure,
    required this.onToggleMode,
    required this.onSubmit,
  });

  final GlobalKey<FormState> formKey;
  final TextEditingController emailCtrl;
  final TextEditingController passCtrl;
  final TextEditingController userCtrl;
  final TextEditingController pass2Ctrl;
  final bool isRegister;
  final bool obscurePass;
  final bool loading;
  final String? error;
  final VoidCallback onToggleObscure;
  final VoidCallback onToggleMode;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final isMobile = MediaQuery.of(context).size.width < 600;

    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topRight,
          end: Alignment.bottomLeft,
          colors: [Color(0xFF1A1030), kBgColor, Color(0xFF150C28)],
          stops: [0.0, 0.55, 1.0],
        ),
      ),
      child: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: 40,
                vertical: isMobile ? 32 : 48,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (isMobile) ...[
                    Center(
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          Container(
                            width: 72,
                            height: 28,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(999),
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFFAA44FF).withValues(alpha: 0.50),
                                  blurRadius: 18,
                                  spreadRadius: 4,
                                ),
                                BoxShadow(
                                  color: const Color(0xFF8822EE).withValues(alpha: 0.25),
                                  blurRadius: 36,
                                  spreadRadius: 8,
                                ),
                              ],
                            ),
                          ),
                          SvgPicture.asset('assets/logo/logo.svg', width: 72, height: 72),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    Center(
                      child: ShaderMask(
                        shaderCallback: (bounds) => const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [kPrimaryLight, kPrimary],
                        ).createShader(bounds),
                        child: const Text(
                          'YGG',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 10,
                            color: Colors.white,
                            height: 1.0,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Center(
                      child: Text(
                        'PRO SCOUTING',
                        style: TextStyle(fontSize: 9, letterSpacing: 4, color: kMuted),
                      ),
                    ),
                    const SizedBox(height: 28),
                  ],
                  Text(
                    isRegister ? 'Create account' : 'Sign in',
                    style: const TextStyle(
                      color: kForeground,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isRegister
                        ? 'Join the analytics platform'
                        : 'Welcome back',
                    style: const TextStyle(color: kMuted, fontSize: 13),
                  ),
                  const SizedBox(height: 32),

                  Form(
                    key: formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _label('Email'),
                        const SizedBox(height: 4),
                        TextFormField(
                          controller: emailCtrl,
                          keyboardType: TextInputType.emailAddress,
                          style: const TextStyle(
                            color: kForeground,
                            fontSize: 13,
                          ),
                          decoration: const InputDecoration(
                            hintText: 'you@email.com',
                          ),
                          validator: (v) {
                            if (v == null || v.trim().isEmpty) {
                              return 'Required';
                            }
                            if (!RegExp(
                              r'^[^@\s]+@[^@\s]+\.[^@\s]+$',
                            ).hasMatch(v.trim())) {
                              return 'Invalid email format';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 16),

                        if (isRegister) ...[
                          _label('Username'),
                          const SizedBox(height: 4),
                          TextFormField(
                            controller: userCtrl,
                            style: const TextStyle(
                              color: kForeground,
                              fontSize: 13,
                            ),
                            decoration: const InputDecoration(
                              hintText: 'scout42',
                            ),
                            validator: (v) {
                              if (v == null || v.trim().isEmpty) {
                                return 'Required';
                              }
                              if (v.trim().length < 3) {
                                return 'Minimum 3 characters';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                        ],

                        _label('Password'),
                        const SizedBox(height: 4),
                        TextFormField(
                          controller: passCtrl,
                          obscureText: obscurePass,
                          style: const TextStyle(
                            color: kForeground,
                            fontSize: 13,
                          ),
                          textInputAction: isRegister
                              ? TextInputAction.next
                              : TextInputAction.done,
                          onFieldSubmitted: isRegister
                              ? null
                              : (_) => onSubmit(),
                          decoration: InputDecoration(
                            hintText: '••••••••',
                            suffixIcon: IconButton(
                              icon: Icon(
                                obscurePass
                                    ? Icons.visibility_off
                                    : Icons.visibility,
                                size: 18,
                                color: kMuted,
                              ),
                              onPressed: onToggleObscure,
                            ),
                          ),
                          validator: (v) {
                            if (v == null || v.isEmpty) return 'Required';
                            if (v.length < 6) return 'Minimum 6 characters';
                            return null;
                          },
                        ),

                        if (isRegister) ...[
                          const SizedBox(height: 16),
                          _label('Confirm password'),
                          const SizedBox(height: 4),
                          TextFormField(
                            controller: pass2Ctrl,
                            obscureText: obscurePass,
                            style: const TextStyle(
                              color: kForeground,
                              fontSize: 13,
                            ),
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) => onSubmit(),
                            decoration: const InputDecoration(
                              hintText: '••••••••',
                            ),
                            validator: (v) {
                              if (v == null || v.isEmpty) return 'Required';
                              if (v != passCtrl.text) {
                                return 'Passwords do not match';
                              }
                              return null;
                            },
                          ),
                        ],

                        if (error != null) ...[
                          const SizedBox(height: 16),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 8,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.red.withValues(alpha: 0.10),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: Colors.red.withValues(alpha: 0.30),
                              ),
                            ),
                            child: Text(
                              error!,
                              style: const TextStyle(
                                color: Colors.redAccent,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],

                        const SizedBox(height: 28),

                        SizedBox(
                          height: 44,
                          child: ElevatedButton(
                            onPressed: loading ? null : onSubmit,
                            child: loading
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : Text(
                                    isRegister ? 'CREATE ACCOUNT' : 'SIGN IN',
                                    style: const TextStyle(
                                      letterSpacing: 2,
                                      fontSize: 13,
                                    ),
                                  ),
                          ),
                        ),
                        const SizedBox(height: 18),

                        InkWell(
                          onTap: onToggleMode,
                          mouseCursor: SystemMouseCursors.click,
                          borderRadius: BorderRadius.circular(4),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              vertical: 4,
                              horizontal: 8,
                            ),
                            child: Text(
                              isRegister
                                  ? 'Already have an account? Sign in'
                                  : 'No account yet? Register',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: kPrimaryLight,
                                fontSize: 12,
                                decoration: TextDecoration.underline,
                                decorationColor: kPrimaryLight,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _label(String text) => Text(
    text.toUpperCase(),
    style: const TextStyle(color: kMuted, fontSize: 10, letterSpacing: 1.2),
  );
}
