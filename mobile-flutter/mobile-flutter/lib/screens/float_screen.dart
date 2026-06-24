import 'package:flutter/material.dart';
import '../services/api_service.dart';

class FloatScreen extends StatefulWidget {
  const FloatScreen({super.key});
  @override
  State<FloatScreen> createState() => _FloatScreenState();
}

class _FloatScreenState extends State<FloatScreen> {
  bool _loading = true;
  Map<String, dynamic> _balance = {};
  List<Map<String, dynamic>> _history = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _loading = true);
    try {
      final balance = await ApiService.get('/float/balance');
      final history = await ApiService.get('/float/history?page=1&limit=20');
      setState(() {
        _balance = balance;
        _history = List<Map<String, dynamic>>.from(history['items'] ?? []);
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _requestTopUp() async {
    final amount = await showDialog<double>(context: context, builder: (_) {
      double val = 0;
      return AlertDialog(
        title: const Text('Request Float Top-Up'),
        content: TextField(
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(labelText: 'Amount (NGN)', prefixText: '₦ '),
          onChanged: (v) => val = double.tryParse(v) ?? 0,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, val), child: const Text('Request')),
        ],
      );
    });
    if (amount != null && amount > 0) {
      try {
        await ApiService.post('/float/request-topup', {'amount': amount});
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Top-up requested')));
        _loadData();
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Float Management')),
      floatingActionButton: FloatingActionButton(onPressed: _requestTopUp, child: const Icon(Icons.add)),
      body: _loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(
        onRefresh: _loadData,
        child: ListView(children: [
          Card(margin: const EdgeInsets.all(16), child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(children: [
              const Text('Available Float', style: TextStyle(fontSize: 14, color: Colors.grey)),
              Text('₦${(_balance['available'] ?? 0).toStringAsFixed(2)}', style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Text('Reserved: ₦${(_balance['reserved'] ?? 0).toStringAsFixed(2)}', style: const TextStyle(color: Colors.orange)),
            ]),
          )),
          const Padding(padding: EdgeInsets.symmetric(horizontal: 16), child: Text('Recent Activity', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
          ..._history.map((h) => ListTile(
            leading: Icon(h['type'] == 'topup' ? Icons.arrow_upward : Icons.arrow_downward,
              color: h['type'] == 'topup' ? Colors.green : Colors.red),
            title: Text('₦${(h['amount'] ?? 0).toStringAsFixed(2)}'),
            subtitle: Text(h['createdAt'] ?? ''),
            trailing: Chip(label: Text(h['status'] ?? 'pending')),
          )),
        ]),
      ),
    );
  }
}
