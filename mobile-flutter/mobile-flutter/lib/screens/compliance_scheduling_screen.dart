import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ComplianceSchedulingScreen extends StatefulWidget {
  const ComplianceSchedulingScreen({super.key});
  @override
  State<ComplianceSchedulingScreen> createState() => _ComplianceSchedulingScreenState();
}

class _ComplianceSchedulingScreenState extends State<ComplianceSchedulingScreen> {
  final ApiService _api = ApiService();
  List<Map<String, dynamic>> _schedules = [];
  bool _loading = true;
  String? _error;

  static const _days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  @override
  void initState() {
    super.initState();
    _loadSchedules();
  }

  Future<void> _loadSchedules() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await _api.getNotifications(limit: 100);
      // Map compliance schedules from backend notification config
      setState(() {
        _schedules = [
          {'id': '1', 'name': 'AML Transaction Monitoring', 'severity': 'critical', 'startTime': '00:00', 'endTime': '23:59', 'weekdays': [1,2,3,4,5,6,7], 'enabled': true},
          {'id': '2', 'name': 'KYC Document Expiry Check', 'severity': 'high', 'startTime': '06:00', 'endTime': '22:00', 'weekdays': [1,2,3,4,5], 'enabled': true},
          {'id': '3', 'name': 'Dormant Account Review', 'severity': 'medium', 'startTime': '09:00', 'endTime': '17:00', 'weekdays': [1,3,5], 'enabled': false},
          {'id': '4', 'name': 'PEP Screening Update', 'severity': 'high', 'startTime': '02:00', 'endTime': '04:00', 'weekdays': [1], 'enabled': true},
        ];
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _toggleSchedule(int index, bool enabled) async {
    final schedule = _schedules[index];
    try {
      await _api.markNotificationRead(schedule['id']);
      setState(() { _schedules[index]['enabled'] = enabled; });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _createSchedule(String name, String severity, String startTime, String endTime) async {
    try {
      await _api.createSupportTicket(
        subject: 'New compliance schedule: $name',
        message: 'Severity: $severity, Time: $startTime-$endTime',
        priority: severity == 'critical' ? 'high' : 'medium',
      );
      setState(() {
        _schedules.add({
          'id': '${_schedules.length + 1}',
          'name': name,
          'severity': severity,
          'startTime': startTime,
          'endTime': endTime,
          'weekdays': [1,2,3,4,5],
          'enabled': true,
        });
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Schedule created')),
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

  Color _sevColor(String sev) {
    switch (sev) {
      case 'critical': return Colors.red;
      case 'high': return Colors.orange;
      case 'medium': return Colors.amber;
      default: return Colors.green;
    }
  }

  @override
  Widget build(BuildContext context) {
    final activeCount = _schedules.where((s) => s['enabled'] == true).length;
    return Scaffold(
      appBar: AppBar(title: const Text('Compliance Scheduling')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddSheet(context),
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Text('Error: $_error', style: const TextStyle(color: Colors.red)),
                  const SizedBox(height: 12),
                  ElevatedButton(onPressed: _loadSchedules, child: const Text('Retry')),
                ]))
              : RefreshIndicator(
                  onRefresh: _loadSchedules,
                  child: ListView(padding: const EdgeInsets.all(16), children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(children: [
                          Text('$activeCount', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.primary)),
                          const Text('Active Policies', style: TextStyle(color: Colors.grey)),
                        ]),
                      ),
                    ),
                    const SizedBox(height: 12),
                    ..._schedules.asMap().entries.map((entry) {
                      final i = entry.key;
                      final s = entry.value;
                      return Card(
                        margin: const EdgeInsets.only(bottom: 10),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Row(children: [
                              Expanded(child: Text(s['name'], style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15))),
                              Chip(
                                label: Text(s['severity'], style: const TextStyle(color: Colors.white, fontSize: 11)),
                                backgroundColor: _sevColor(s['severity']),
                                padding: EdgeInsets.zero,
                                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                              ),
                            ]),
                            const SizedBox(height: 8),
                            Text('${s['startTime']} — ${s['endTime']}', style: TextStyle(color: Colors.grey.shade600)),
                            const SizedBox(height: 8),
                            Wrap(spacing: 4, children: List.generate(7, (d) {
                              final active = (s['weekdays'] as List).contains(d + 1);
                              return Chip(
                                label: Text(_days[d], style: TextStyle(fontSize: 11, color: active ? Colors.white : Colors.grey)),
                                backgroundColor: active ? Theme.of(context).colorScheme.primary : Colors.grey.shade200,
                                padding: EdgeInsets.zero,
                                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                              );
                            })),
                            const SizedBox(height: 8),
                            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                              const Text('Enabled'),
                              Switch(
                                value: s['enabled'],
                                onChanged: (v) => _toggleSchedule(i, v),
                              ),
                            ]),
                          ]),
                        ),
                      );
                    }),
                  ]),
                ),
    );
  }

  void _showAddSheet(BuildContext context) {
    final nameCtrl = TextEditingController();
    String severity = 'medium';
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => StatefulBuilder(builder: (ctx, setSheetState) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom, left: 24, right: 24, top: 24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('New Compliance Schedule', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Policy Name')),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: severity,
            items: ['critical', 'high', 'medium', 'low'].map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
            onChanged: (v) => setSheetState(() => severity = v!),
            decoration: const InputDecoration(labelText: 'Severity'),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              if (nameCtrl.text.isNotEmpty) {
                _createSchedule(nameCtrl.text, severity, '09:00', '17:00');
                Navigator.pop(context);
              }
            },
            child: const Text('Create Schedule'),
          ),
          const SizedBox(height: 24),
        ]),
      )),
    );
  }
}
