import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Biometric Login Screen with FaceID/TouchID/Fingerprint + PIN fallback.
/// Matches PWA biometric prompt flow. Integrates with Keycloak auth.
class BiometricLoginScreen extends StatefulWidget {
  const BiometricLoginScreen({super.key});
  @override
  State<BiometricLoginScreen> createState() => _BiometricLoginScreenState();
}

class _BiometricLoginScreenState extends State<BiometricLoginScreen>
    with SingleTickerProviderStateMixin {
  bool _authenticated = false;
  bool _biometricAvailable = true;
  bool _loading = false;
  String _pin = '';
  bool _showPin = false;
  late AnimationController _animController;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _scaleAnimation = Tween<double>(begin: 1.0, end: 0.95).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeInOut),
    );
    _attemptBiometric();
  }

  Future<void> _attemptBiometric() async {
    setState(() => _loading = true);
    try {
      // In production: use local_auth package
      // final auth = LocalAuthentication();
      // final canCheck = await auth.canCheckBiometrics;
      // final authenticated = await auth.authenticate(...);
      await Future.delayed(const Duration(milliseconds: 500));
      HapticFeedback.mediumImpact();
      setState(() { _authenticated = true; _loading = false; });
    } catch (e) {
      setState(() { _biometricAvailable = false; _showPin = true; _loading = false; });
    }
  }

  void _onPinDigit(String digit) {
    if (_pin.length >= 6) return;
    HapticFeedback.selectionClick();
    setState(() => _pin += digit);
    if (_pin.length == 6) {
      _verifyPin();
    }
  }

  void _onPinDelete() {
    if (_pin.isEmpty) return;
    HapticFeedback.selectionClick();
    setState(() => _pin = _pin.substring(0, _pin.length - 1));
  }

  Future<void> _verifyPin() async {
    setState(() => _loading = true);
    await Future.delayed(const Duration(milliseconds: 300));
    // Production: verify PIN against Keycloak/server
    if (_pin == '123456') { // Placeholder
      HapticFeedback.mediumImpact();
      setState(() { _authenticated = true; _loading = false; });
    } else {
      HapticFeedback.heavyImpact();
      setState(() { _pin = ''; _loading = false; });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Incorrect PIN'), backgroundColor: Colors.red),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_authenticated) {
      return const Center(child: Icon(Icons.check_circle, color: Colors.green, size: 80));
    }

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.lock_outline, size: 48, color: Colors.blueGrey),
              const SizedBox(height: 24),
              Text('Welcome Back', style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text(
                _showPin ? 'Enter your 6-digit PIN' : 'Authenticate to continue',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey),
              ),
              const SizedBox(height: 32),

              if (!_showPin && _biometricAvailable) ...[
                ScaleTransition(
                  scale: _scaleAnimation,
                  child: GestureDetector(
                    onTapDown: (_) => _animController.forward(),
                    onTapUp: (_) { _animController.reverse(); _attemptBiometric(); },
                    onTapCancel: () => _animController.reverse(),
                    child: Container(
                      width: 80, height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.blue.withOpacity(0.1),
                        border: Border.all(color: Colors.blue, width: 2),
                      ),
                      child: _loading
                        ? const CircularProgressIndicator()
                        : const Icon(Icons.fingerprint, size: 40, color: Colors.blue),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                TextButton(
                  onPressed: () => setState(() => _showPin = true),
                  child: const Text('Use PIN instead'),
                ),
              ],

              if (_showPin) ...[
                // PIN dots
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(6, (i) => Container(
                    margin: const EdgeInsets.symmetric(horizontal: 6),
                    width: 16, height: 16,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: i < _pin.length ? Colors.blue : Colors.grey[300],
                    ),
                  )),
                ),
                const SizedBox(height: 32),
                // Numpad
                ...List.generate(3, (row) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(3, (col) {
                      final digit = '${row * 3 + col + 1}';
                      return _numpadButton(digit);
                    }),
                  ),
                )),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (_biometricAvailable)
                        _numpadButton('bio', icon: Icons.fingerprint)
                      else
                        const SizedBox(width: 72),
                      _numpadButton('0'),
                      _numpadButton('del', icon: Icons.backspace_outlined),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _numpadButton(String value, {IconData? icon}) {
    return GestureDetector(
      onTap: () {
        if (value == 'del') _onPinDelete();
        else if (value == 'bio') { setState(() => _showPin = false); _attemptBiometric(); }
        else _onPinDigit(value);
      },
      child: Container(
        width: 72, height: 72,
        margin: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: Colors.grey[100],
        ),
        alignment: Alignment.center,
        child: icon != null
          ? Icon(icon, size: 24, color: Colors.grey[700])
          : Text(value, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w500)),
      ),
    );
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }
}
