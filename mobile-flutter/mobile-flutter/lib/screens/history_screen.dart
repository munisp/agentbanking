import 'package:flutter/material.dart';
import '../services/api_service.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  bool _loading = true;
  List<Map<String, dynamic>> _transactions = [];
  int _page = 1;
  String _filter = 'all';

  @override
  void initState() {
    super.initState();
    _loadTransactions();
  }

  Future<void> _loadTransactions() async {
    setState(() => _loading = true);
    try {
      final filterParam = _filter != 'all' ? '&type=$_filter' : '';
      final data = await ApiService.get('/transactions/list?page=$_page&limit=30$filterParam');
      setState(() => _transactions = List<Map<String, dynamic>>.from(data['items'] ?? []));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Transaction History'), actions: [
        PopupMenuButton<String>(
          onSelected: (v) { setState(() { _filter = v; _page = 1; }); _loadTransactions(); },
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'all', child: Text('All')),
            const PopupMenuItem(value: 'cash_in', child: Text('Cash In')),
            const PopupMenuItem(value: 'cash_out', child: Text('Cash Out')),
            const PopupMenuItem(value: 'transfer', child: Text('Transfer')),
            const PopupMenuItem(value: 'bill_payment', child: Text('Bill Payment')),
          ],
        ),
      ]),
      body: _loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(
        onRefresh: _loadTransactions,
        child: ListView.builder(
          itemCount: _transactions.length,
          itemBuilder: (_, i) {
            final tx = _transactions[i];
            return ListTile(
              leading: CircleAvatar(child: Text(tx['type']?.toString().substring(0, 1).toUpperCase() ?? '?')),
              title: Text('₦${(tx['amount'] ?? 0).toStringAsFixed(2)}'),
              subtitle: Text('${tx['type'] ?? 'unknown'} • ${tx['createdAt'] ?? ''}'),
              trailing: Text(tx['status'] ?? '', style: TextStyle(
                color: tx['status'] == 'completed' ? Colors.green : tx['status'] == 'failed' ? Colors.red : Colors.orange,
              )),
            );
          },
        ),
      ),
    );
  }
}
