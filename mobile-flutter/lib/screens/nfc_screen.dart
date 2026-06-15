import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';

class NfcScreen extends ConsumerStatefulWidget {
  const NfcScreen({super.key});

  @override
  ConsumerState<NfcScreen> createState() => _NfcScreenState();
}

class _NfcScreenState extends ConsumerState<NfcScreen> {
  Map<String, dynamic>? _stats;
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String _error = '';
  String _searchQuery = '';

  @override
  void initState() { super.initState(); _loadData(); }

  Future<void> _loadData() async {
    setState(() => _loading = true);
    try {
      final api = ApiService();
      final statsResp = await api.get('/api/trpc/nfc.getStats');
      final listResp = await api.get('/api/trpc/nfc.list?input={"limit":20,"offset":0}');
      setState(() {
        _stats = statsResp.data?['result']?['data'] ?? {};
        _items = List<Map<String, dynamic>>.from(listResp.data?['result']?['data']?['items'] ?? []);
        _loading = false;
      });
    } catch (e) { setState(() { _error = e.toString(); _loading = false; }); }
  }

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
    return Card(elevation: 2, child: Padding(padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
        Row(children: [Icon(icon, size: 16, color: color), const SizedBox(width: 6), Flexible(child: Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[600]), overflow: TextOverflow.ellipsis))]),
        const SizedBox(height: 8),
        Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold), overflow: TextOverflow.ellipsis),
      ])));
  }

  Widget _buildNfcSignalStrength(Map<String, dynamic> item) {
    final strength = int.tryParse('${item[\'signalStrength\'] ?? 0}') ?? 0;
    final bars = (strength / 25).ceil().clamp(0, 4);
    return Row(children: List.generate(4, (i) => Container(width: 6, height: 8.0 + i * 4, margin: const EdgeInsets.only(right: 2), decoration: BoxDecoration(color: i < bars ? Colors.green : Colors.grey[300], borderRadius: BorderRadius.circular(2)))));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final filtered = _searchQuery.isEmpty ? _items : _items.where((item) => item.values.any((v) => '$v'.toLowerCase().contains(_searchQuery.toLowerCase()))).toList();

    return Scaffold(
      appBar: AppBar(
        title: Row(children: [Icon(Icons.nfc, size: 24), const SizedBox(width: 8), const Text('NFC Tap-to-Pay')]),
        actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _loadData)],
      ),
      body: _loading ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.error_outline, size: 48, color: theme.colorScheme.error), const SizedBox(height: 16),
              Text(_error, textAlign: TextAlign.center), const SizedBox(height: 16),
              ElevatedButton(onPressed: _loadData, child: const Text('Retry'))]))
          : RefreshIndicator(onRefresh: _loadData, child: CustomScrollView(slivers: [
              SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('NFC Tap-to-Pay', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('Turn any Android phone into a POS terminal', style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey)),
              ]))),
              SliverPadding(padding: const EdgeInsets.symmetric(horizontal: 16),
                sliver: SliverGrid(gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 12, crossAxisSpacing: 12, childAspectRatio: 1.6),
                  delegate: SliverChildListDelegate([
                              _buildStatCard('Active Terminals', '${_stats?['activeTerminals'] ?? '\u2014'}', Icons.phone_android, Colors.blue),
                              _buildStatCard('Today\'s Taps', '${_stats?['transactionsToday'] ?? '\u2014'}', Icons.touch_app, Colors.green),
                              _buildStatCard('Today\'s Volume', '₦${_stats?['volumeToday'] ?? '\u2014'}', Icons.attach_money, Colors.orange),
                              _buildStatCard('Avg Tap Time', '${_stats?['avgTapTime'] ?? '\u2014'}', Icons.timer, Colors.purple),
                  ]))),
              SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.all(16), child: TextField(
                onChanged: (v) => setState(() => _searchQuery = v),
                decoration: InputDecoration(hintText: 'Search records...', prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)), contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12))))),
              SliverPadding(padding: const EdgeInsets.symmetric(horizontal: 16),
                sliver: SliverToBoxAdapter(child: Text('Records (${filtered.length})', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)))),
              SliverList(delegate: SliverChildBuilderDelegate((context, index) {
                final item = filtered[index];
                return Card(margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: ListTile(leading: CircleAvatar(backgroundColor: theme.colorScheme.primaryContainer,
                    child: Text('${item[\'id\'] ?? index + 1}', style: TextStyle(color: theme.colorScheme.onPrimaryContainer, fontWeight: FontWeight.bold))),
                    title: Text('${item['terminalId'] ?? item['deviceModel'] ?? \'Record #${item[\'id\']}\'}', overflow: TextOverflow.ellipsis),
                    subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Status: ${item[\'status\'] ?? \'\u2014\'}', style: const TextStyle(fontSize: 12)),
                      const SizedBox(height: 4),
                      _buildNfcSignalStrength(item),
                    ]),
                    trailing: Icon(Icons.chevron_right, color: Colors.grey[400]), isThreeLine: true));
              }, childCount: filtered.length)),
              const SliverPadding(padding: EdgeInsets.only(bottom: 32)),
            ])),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showPaymentDialog,
        icon: const Icon(Icons.nfc),
        label: const Text('New Payment'),
        backgroundColor: const Color(0xFF0D7377),
      ),
    );
  }

  void _showPaymentDialog() {
    final amountController = TextEditingController();
    final terminalController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('NFC Tap-to-Pay'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: amountController, decoration: const InputDecoration(labelText: 'Amount (₦)', prefixText: '₦'), keyboardType: TextInputType.number),
            const SizedBox(height: 12),
            TextField(controller: terminalController, decoration: const InputDecoration(labelText: 'Terminal ID')),
            const SizedBox(height: 16),
            const Text('Hold customer\'s contactless card near the device', style: TextStyle(color: Colors.grey, fontSize: 12)),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              final amount = double.tryParse(amountController.text);
              if (amount == null || amount <= 0) return;
              Navigator.pop(ctx);
              setState(() => _loading = true);
              try {
                final api = ApiService();
                final resp = await api.post('/api/trpc/nfcTapToPay.processPayment', data: {
                  'terminalId': terminalController.text.isNotEmpty ? terminalController.text : 'TERM-001',
                  'amount': amount,
                  'cardType': 'unknown',
                  'agentId': 1,
                });
                final result = resp.data?['result']?['data'];
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                    content: Text('Payment completed: ${result?['reference']} — ₦$amount'),
                    backgroundColor: Colors.green,
                  ));
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Payment failed: $e'), backgroundColor: Colors.red));
                }
              }
              _loadData();
            },
            child: const Text('Process Payment'),
          ),
        ],
      ),
    );
  }
}
