import 'package:flutter/material.dart';
import '../services/api_service.dart';


class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key});
  @override
  State<NotificationPreferencesScreen> createState() => _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState extends State<NotificationPreferencesScreen> {
  final Map<String, Map<String, bool>> _prefs = {
    'Transaction Alerts': {'Push': true, 'SMS': true, 'Email': false},
    'Security Alerts': {'Push': true, 'SMS': true, 'Email': true},
    'Performance Updates': {'Push': true, 'SMS': false, 'Email': false},
    'System Notifications': {'Push': true, 'SMS': false, 'Email': false},
  };
  TimeOfDay _quietStart = const TimeOfDay(hour: 22, minute: 0);
  TimeOfDay _quietEnd = const TimeOfDay(hour: 7, minute: 0);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notification Preferences')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Preferences saved'))),
        icon: const Icon(Icons.save),
        label: const Text('Save'),
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
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
        // Quiet Hours
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
        // Test notification
        OutlinedButton.icon(
          onPressed: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Test notification sent'))),
          icon: const Icon(Icons.notifications_active),
          label: const Text('Send Test Notification'),
        ),
        const SizedBox(height: 80),
      ]),
    );
  }
}
