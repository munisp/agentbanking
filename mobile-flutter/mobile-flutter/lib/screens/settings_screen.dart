import 'package:flutter/material.dart';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _biometricEnabled = false;
  bool _pushEnabled = true;
  String _language = 'en';

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final data = await ApiService.get('/settings/preferences');
      setState(() {
        _biometricEnabled = data['biometricEnabled'] ?? false;
        _pushEnabled = data['pushEnabled'] ?? true;
        _language = data['language'] ?? 'en';
      });
    } catch (_) {}
  }

  Future<void> _updateSetting(String key, dynamic value) async {
    try {
      await ApiService.post('/settings/update', {key: value});
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(children: [
        const ListTile(title: Text('Security', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue))),
        SwitchListTile(
          title: const Text('Biometric Login'), subtitle: const Text('Use fingerprint or face ID'),
          value: _biometricEnabled,
          onChanged: (v) { setState(() => _biometricEnabled = v); _updateSetting('biometricEnabled', v); },
        ),
        ListTile(title: const Text('Change PIN'), trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.pushNamed(context, '/change-pin')),
        const Divider(),
        const ListTile(title: Text('Notifications', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue))),
        SwitchListTile(
          title: const Text('Push Notifications'),
          value: _pushEnabled,
          onChanged: (v) { setState(() => _pushEnabled = v); _updateSetting('pushEnabled', v); },
        ),
        const Divider(),
        const ListTile(title: Text('Language', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue))),
        RadioListTile(title: const Text('English'), value: 'en', groupValue: _language,
          onChanged: (v) { setState(() => _language = v!); _updateSetting('language', v); }),
        RadioListTile(title: const Text('Hausa'), value: 'ha', groupValue: _language,
          onChanged: (v) { setState(() => _language = v!); _updateSetting('language', v); }),
        RadioListTile(title: const Text('Yoruba'), value: 'yo', groupValue: _language,
          onChanged: (v) { setState(() => _language = v!); _updateSetting('language', v); }),
        RadioListTile(title: const Text('Pidgin'), value: 'pcm', groupValue: _language,
          onChanged: (v) { setState(() => _language = v!); _updateSetting('language', v); }),
        const Divider(),
        ListTile(title: const Text('About'), subtitle: const Text('Version 1.0.0'),
          trailing: const Icon(Icons.info_outline)),
      ]),
    );
  }
}
