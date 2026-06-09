import 'package:flutter/material.dart';

class SettlementScreen extends StatefulWidget {
  const SettlementScreen({super.key});
  @override
  State<SettlementScreen> createState() => _SettlementScreenState();
}

class _SettlementScreenState extends State<SettlementScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _data = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      setState(() => _isLoading = true);
      await Future.delayed(const Duration(milliseconds: 500));
      setState(() { _isLoading = false; _data = []; });
    } catch (e) {
      setState(() { _isLoading = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settlement Status'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadData),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 16),
            Text(_error!, style: const TextStyle(color: Colors.red)),
            ElevatedButton(onPressed: _loadData, child: const Text('Retry')),
          ],
        ),
      );
    }
    if (_data.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.inbox, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text('No data yet', style: TextStyle(fontSize: 18, color: Colors.grey[600])),
            Text('Track settlement batches and reconciliation', style: TextStyle(color: Colors.grey[500]), textAlign: TextAlign.center),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView.builder(
        itemCount: _data.length,
        padding: const EdgeInsets.all(16),
        itemBuilder: (context, index) {
          final item = _data[index];
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: ListTile(
              title: Text(item['title'] ?? 'Item ${index + 1}'),
              subtitle: Text(item['subtitle'] ?? ''),
              trailing: const Icon(Icons.chevron_right),
            ),
          );
        },
      ),
    );
  }
}
