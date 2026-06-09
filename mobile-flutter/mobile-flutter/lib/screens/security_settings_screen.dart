import 'package:flutter/material.dart';
import '../services/api_service.dart';

class SecuritySettingsScreen extends StatefulWidget {
  const SecuritySettingsScreen({super.key});
  @override
  State<SecuritySettingsScreen> createState() => _SecuritySettingsScreenState();
}

class _SecuritySettingsScreenState extends State<SecuritySettingsScreen> {
  bool _biometricEnabled = false;
  bool _twoFaEnabled = false;
  bool _loading = false;

  Future<void> _toggle(String setting, bool value) async {
    setState(() => _loading = true);
    try {
      await ApiService.instance.updateSecuritySetting(setting, value);
      setState(() {
        if (setting == 'biometric') _biometricEnabled = value;
        if (setting == 'two_fa') _twoFaEnabled = value;
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Security Settings')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(children: [
            SwitchListTile(
              title: const Text('Biometric Login'),
              subtitle: const Text('Use fingerprint or face ID'),
              value: _biometricEnabled,
              onChanged: (v) => _toggle('biometric', v),
            ),
            SwitchListTile(
              title: const Text('Two-Factor Authentication'),
              subtitle: const Text('TOTP via authenticator app'),
              value: _twoFaEnabled,
              onChanged: (v) => _toggle('two_fa', v),
            ),
            ListTile(
              leading: const Icon(Icons.lock_reset),
              title: const Text('Change PIN'),
              onTap: () => Navigator.pushNamed(context, '/pin-setup'),
            ),
            ListTile(
              leading: const Icon(Icons.devices),
              title: const Text('Active Sessions'),
              onTap: () => Navigator.pushNamed(context, '/active-sessions'),
            ),
          ]),
  );
}
