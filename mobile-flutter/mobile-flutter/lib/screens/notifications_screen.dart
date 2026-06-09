import 'package:flutter/material.dart';
import '../services/api_service.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getNotifications();
      setState(() { _items = List<Map<String, dynamic>>.from(data); _loading = false; });
    } catch (_) { setState(() { _loading = false; }); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Notifications')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _items.isEmpty
            ? const Center(child: Text('No notifications'))
            : ListView.separated(
                itemCount: _items.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (_, i) {
                  final n = _items[i];
                  return ListTile(
                    leading: Icon(n['read'] == true ? Icons.notifications_none : Icons.notifications,
                        color: n['read'] == true ? Colors.grey : Theme.of(context).colorScheme.primary),
                    title: Text(n['title'] ?? ''),
                    subtitle: Text(n['body'] ?? ''),
                    trailing: Text(n['created_at'] != null
                        ? DateTime.fromMillisecondsSinceEpoch(n['created_at']).toString().split(' ')[0]
                        : '', style: const TextStyle(fontSize: 11, color: Colors.grey)),
                  );
                }),
  );
}
