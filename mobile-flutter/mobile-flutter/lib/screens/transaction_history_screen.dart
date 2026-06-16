import 'package:flutter/material.dart';
import '../services/api_service.dart';

class TransactionHistoryScreen extends StatefulWidget {
  const TransactionHistoryScreen({super.key});
  @override
  State<TransactionHistoryScreen> createState() => _TransactionHistoryScreenState();
}

class _TransactionHistoryScreenState extends State<TransactionHistoryScreen> {
  List<Map<String, dynamic>> _txs = [];
  bool _loading = true;
  int _page = 1;
  bool _hasMore = true;
  final _scrollCtrl = ScrollController();

  @override
  void initState() {
    super.initState();
    _load();
    _scrollCtrl.addListener(() {
      if (_scrollCtrl.position.pixels >= _scrollCtrl.position.maxScrollExtent - 100 && _hasMore) {
        _loadMore();
      }
    });
  }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getTransactions(page: 1, limit: 20);
      setState(() {
        _txs = List<Map<String, dynamic>>.from(data['items'] ?? data);
        _hasMore = (data['hasMore'] ?? false);
        _loading = false;
      });
    } catch (_) { setState(() => _loading = false); }
  }

  Future<void> _loadMore() async {
    if (!_hasMore) return;
    _page++;
    try {
      final data = await ApiService.instance.getTransactions(page: _page, limit: 20);
      final items = List<Map<String, dynamic>>.from(data['items'] ?? data);
      setState(() {
        _txs.addAll(items);
        _hasMore = data['hasMore'] ?? items.length == 20;
      });
    } catch (_) {}
  }

  @override
  void dispose() { _scrollCtrl.dispose(); super.dispose(); }

  Color _statusColor(String? status) {
    switch (status) {
      case 'completed': return Colors.green;
      case 'failed': return Colors.red;
      case 'pending': return Colors.orange;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Transaction History')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _txs.isEmpty
            ? const Center(child: Text('No transactions yet'))
            : ListView.separated(
                controller: _scrollCtrl,
                itemCount: _txs.length + (_hasMore ? 1 : 0),
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (_, i) {
                  if (i == _txs.length) return const Center(child: Padding(
                    padding: EdgeInsets.all(16), child: CircularProgressIndicator()));
                  final tx = _txs[i];
                  final isCredit = tx['type'] == 'credit';
                  return ListTile(
                    leading: CircleAvatar(
                      backgroundColor: isCredit ? Colors.green.shade50 : Colors.red.shade50,
                      child: Icon(isCredit ? Icons.arrow_downward : Icons.arrow_upward,
                          color: isCredit ? Colors.green : Colors.red),
                    ),
                    title: Text(tx['narration'] ?? tx['type'] ?? ''),
                    subtitle: Text(tx['created_at'] != null
                        ? DateTime.fromMillisecondsSinceEpoch(tx['created_at']).toString()
                        : ''),
                    trailing: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Text('₦${((tx['amount'] ?? 0) / 100).toStringAsFixed(2)}',
                          style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: isCredit ? Colors.green : Colors.red)),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: _statusColor(tx['status']).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4)),
                        child: Text(tx['status'] ?? '',
                            style: TextStyle(fontSize: 10, color: _statusColor(tx['status']))),
                      ),
                    ]),
                    onTap: () => Navigator.pushNamed(context, '/transaction-detail',
                        arguments: tx),
                  );
                }),
  );
}
