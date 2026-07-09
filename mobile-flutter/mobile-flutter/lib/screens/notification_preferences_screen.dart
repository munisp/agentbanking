import 'package:flutter/material.dart';
import '../services/api_service.dart';

class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key});
  @override
  State<NotificationPreferencesScreen> createState() => _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState extends State<NotificationPreferencesScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  bool _saving = false;
  String? _error;

  final Map<String, Map<String, bool>> _prefs = {
    'Transaction Alerts': {'Push': true, 'SMS': true, 'Email': false},
    'Security Alerts': {'Push': true, 'SMS': true, 'Email': true},
    'Performance Updates': {'Push': true, 'SMS': false, 'Email': false},
    'System Notifications': {'Push': true, 'SMS': false, 'Email': false},
  };
  TimeOfDay _quietStart = const TimeOfDay(hour: 22, minute: 0);
  TimeOfDay _quietEnd = const TimeOfDay(hour: 7, minute: 0);

  @override
  void initState() {
    super.initState();
    _loadPrefs();
  }

  Future<void> _loadPrefs() async {
    setState(() { _loading = true; _error = null; });
    try {
      final profile = await _api.getProfile();
      if (profile['notificationPrefs'] is Map) {
        final saved = profile['notificationPrefs'] as Map;
        for (final section in _prefs.keys) {
          if (saved[section] is Map) {
            final savedSection = saved[section] as Map;
            for (final channel in _prefs[section]!.keys) {
              if (savedSection[channel] is bool) {
                _prefs[section]![channel] = savedSection[channel] as bool;
              }
            }
          }
        }
      }
      setState(() => _loading = false);
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _savePrefs() async {
    setState(() => _saving = true);
    try {
      await _api.updateProfile();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Preferences saved')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Save failed: $e'), backgroundColor: Colors.red),
        );
      }
    }
    setState(() => _saving = false);
  }

  Future<void> _sendTestNotification() async {
    try {
      await _api.createSupportTicket(
        subject: 'Test notification',
        message: 'Testing notification delivery',
        priority: 'low',
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Test notification sent')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notification Preferences')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _saving ? null : _savePrefs,
        icon: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.save),
        label: Text(_saving ? 'Saving...' : 'Save'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Text('Error: $_error', style: const TextStyle(color: Colors.red)),
                  const SizedBox(height: 12),
                  ElevatedButton(onPressed: _loadPrefs, child: const Text('Retry')),
                ]))
              : RefreshIndicator(
                  onRefresh: _loadPrefs,
                  child: ListView(padding: const EdgeInsets.all(16), children: [
                    ..._prefs.entries.map((section) => Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ExpansionTile(
                        title: Text(section.key, style: const TextStyle(fontWeight: FontWeight.w600)),
                        initiallyExpanded: true,
                        children: section.value.entries.map((ch) => SwitchListTile(
                          title: Text(ch.key),
                          value: ch.value,
                          onChanged: (v) => setState(() => _prefs[section.key]![ch.key] = v),
                        )).toList(),
                      ),
                    )),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          const Text('Quiet Hours', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
                          const SizedBox(height: 12),
                          Row(children: [
                            Expanded(child: ListTile(
                              title: const Text('Start'),
                              trailing: Text(_quietStart.format(context), style: TextStyle(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w600)),
                              onTap: () async {
                                final t = await showTimePicker(context: context, initialTime: _quietStart);
                                if (t != null) setState(() => _quietStart = t);
                              },
                            )),
                            Expanded(child: ListTile(
                              title: const Text('End'),
                              trailing: Text(_quietEnd.format(context), style: TextStyle(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w600)),
                              onTap: () async {
                                final t = await showTimePicker(context: context, initialTime: _quietEnd);
                                if (t != null) setState(() => _quietEnd = t);
                              },
                            )),
                          ]),
                        ]),
                      ),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _sendTestNotification,
                      icon: const Icon(Icons.notifications_active),
                      label: const Text('Send Test Notification'),
                    ),
                    const SizedBox(height: 80),
                  ]),
                ),
    );
  }
}
