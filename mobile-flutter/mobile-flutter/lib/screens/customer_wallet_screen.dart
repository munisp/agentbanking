import 'package:flutter/material.dart';
import '../services/api_service.dart';

class CustomerWalletScreen extends StatefulWidget {
  const CustomerWalletScreen({super.key});
  @override
  State<CustomerWalletScreen> createState() => _CustomerWalletScreenState();
}

class _CustomerWalletScreenState extends State<CustomerWalletScreen> {
  Map<String, dynamic>? _wallet;
  List<dynamic> _transactions = [];
  bool _loading = true;
  String _search = '';

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final wallet = await ApiService.instance.getCustomerWallet();
      final txRes = await ApiService.instance.getCustomerTransactions();
      setState(() {
        _wallet = wallet;
        _transactions = txRes;
        _loading = false;
      });
    } catch (_) { setState(() => _loading = false); }
  }

  String _fmt(num v) => '₦${(v / 100).toStringAsFixed(2)}';

  List<dynamic> get _filtered => _transactions.where((t) {
    final q = _search.toLowerCase();
    return (t['description'] ?? '').toString().toLowerCase().contains(q) ||
           (t['type'] ?? '').toString().toLowerCase().contains(q);
  }).toList();

  @override
  Widget build(BuildContext context) {
    final balance = _wallet?['balance'] ?? 0;
    final creditLimit = _wallet?['creditLimit'] ?? 0;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Customer Wallet')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(children: [
                // Balance Card
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: [theme.colorScheme.primary, theme.colorScheme.primary.withOpacity(0.7)]),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(children: [
                    const Text('Available Balance', style: TextStyle(color: Colors.white70, fontSize: 14)),
                    Text(_fmt(balance), style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    Text('Credit Limit: ${_fmt(creditLimit)}', style: const TextStyle(color: Colors.white60, fontSize: 12)),
                  ]),
                ),
                // Actions
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
                    _actionBtn(Icons.add_circle_outline, 'Top Up'),
                    _actionBtn(Icons.send, 'Send'),
                    _actionBtn(Icons.ac_unit, 'Freeze'),
                    _actionBtn(Icons.history, 'History'),
                  ]),
                ),
                const SizedBox(height: 16),
                // Search
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: TextField(
                    decoration: const InputDecoration(hintText: 'Search transactions...', prefixIcon: Icon(Icons.search)),
                    onChanged: (v) => setState(() => _search = v),
                  ),
                ),
                const SizedBox(height: 8),
                // Transaction list
                ..._filtered.map((t) {
                  final isCredit = (t['amount'] ?? 0) > 0;
                  return ListTile(
                    leading: CircleAvatar(
                      backgroundColor: isCredit ? Colors.green.shade100 : Colors.red.shade100,
                      child: Icon(isCredit ? Icons.arrow_downward : Icons.arrow_upward,
                          color: isCredit ? Colors.green : Colors.red),
                    ),
                    title: Text(t['description'] ?? t['type'] ?? ''),
                    subtitle: Text(DateTime.tryParse(t['createdAt'] ?? '')?.toLocal().toString().substring(0, 16) ?? ''),
                    trailing: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Text('${isCredit ? '+' : ''}${_fmt(t['amount'] ?? 0)}',
                          style: TextStyle(color: isCredit ? Colors.green : Colors.red, fontWeight: FontWeight.w600)),
                      Chip(
                        label: Text(t['status'] ?? '', style: const TextStyle(fontSize: 10)),
                        padding: EdgeInsets.zero,
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                    ]),
                  );
                }),
                if (_filtered.isEmpty)
                  const Padding(padding: EdgeInsets.all(40), child: Center(child: Text('No transactions'))),
              ]),
            ),
    );
  }

  Widget _actionBtn(IconData icon, String label) => Column(children: [
    IconButton(
      icon: Icon(icon, color: Theme.of(context).colorScheme.primary),
      onPressed: () => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$label coming soon'))),
    ),
    Text(label, style: const TextStyle(fontSize: 12)),
  ]);
}
