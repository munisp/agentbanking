import 'package:flutter/material.dart';
import '../services/api_service.dart';


class AuditExportScreen extends StatefulWidget {
  const AuditExportScreen({super.key});
  @override
  State<AuditExportScreen> createState() => _AuditExportScreenState();
}

class _AuditExportScreenState extends State<AuditExportScreen> {
  DateTime _from = DateTime(2026, 4, 1);
  DateTime _to = DateTime.now();
  String _actionType = 'All';
  int? _previewCount;
  bool _loading = false;

  final _actionTypes = ['All', 'login', 'transaction', 'config_change', 'user_action', 'system'];
  final List<Map<String, String>> _recentExports = [
    {'filename': 'audit_2026-04-01_2026-04-15.csv', 'date': '2026-04-15', 'size': '2.4 MB', 'format': 'CSV'},
    {'filename': 'audit_2026-03-01_2026-03-31.pdf', 'date': '2026-04-01', 'size': '5.1 MB', 'format': 'PDF'},
  ];

  Future<void> _pickDate(bool isFrom) async {
    final d = await showDatePicker(
      context: context,
      initialDate: isFrom ? _from : _to,
      firstDate: DateTime(2024),
      lastDate: DateTime.now(),
    );
    if (d != null) setState(() { if (isFrom) _from = d; else _to = d; });
  }

  void _preview() {
    setState(() { _loading = true; });
    Future.delayed(const Duration(milliseconds: 500), () {
      setState(() { _previewCount = 1247; _loading = false; });
    });
  }

  void _export(String format) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${format.toUpperCase()} export started')));
  }

  String _fmtDate(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Audit Export')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        // Date Range
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Date Range', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: OutlinedButton(
                  onPressed: () => _pickDate(true),
                  child: Text('From: ${_fmtDate(_from)}'),
                )),
                const SizedBox(width: 12),
                Expanded(child: OutlinedButton(
                  onPressed: () => _pickDate(false),
                  child: Text('To: ${_fmtDate(_to)}'),
                )),
              ]),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        // Filters
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Filters', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _actionType,
                items: _actionTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                onChanged: (v) => setState(() => _actionType = v!),
                decoration: const InputDecoration(labelText: 'Action Type'),
              ),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        // Preview
        ElevatedButton(
          onPressed: _loading ? null : _preview,
          style: ElevatedButton.styleFrom(backgroundColor: Colors.grey.shade700),
          child: Text(_loading ? 'Loading...' : 'Preview Results'),
        ),
        if (_previewCount != null) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(children: [
                Text('$_previewCount', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: theme.colorScheme.primary)),
                const Text('matching records', style: TextStyle(color: Colors.grey)),
              ]),
            ),
          ),
        ],
        const SizedBox(height: 12),
        // Export buttons
        Row(children: [
          Expanded(child: OutlinedButton(onPressed: () => _export('csv'), child: const Text('Export CSV'))),
          const SizedBox(width: 12),
          Expanded(child: ElevatedButton(onPressed: () => _export('pdf'), child: const Text('Export PDF'))),
        ]),
        const SizedBox(height: 24),
        // Recent Exports
        const Text('Recent Exports', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
        const SizedBox(height: 8),
        ..._recentExports.map((e) => ListTile(
          title: Text(e['filename']!, style: const TextStyle(fontSize: 14)),
          subtitle: Text('${e['date']} · ${e['size']} · ${e['format']}', style: const TextStyle(fontSize: 12)),
          trailing: IconButton(icon: const Icon(Icons.download), onPressed: () {}),
        )),
      ]),
    );
  }
}
