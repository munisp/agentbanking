import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ReceiptScreen extends StatefulWidget {
  final String txRef;
  const ReceiptScreen({super.key, required this.txRef});
  @override
  State<ReceiptScreen> createState() => _ReceiptScreenState();
}

class _ReceiptScreenState extends State<ReceiptScreen> {
  bool _loading = true;
  Map<String, dynamic> _receipt = {};

  @override
  void initState() {
    super.initState();
    _loadReceipt();
  }

  Future<void> _loadReceipt() async {
    try {
      final data = await ApiService.get('/transactions/receipt/${widget.txRef}');
      setState(() { _receipt = data; _loading = false; });
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Receipt')),
      body: _loading ? const Center(child: CircularProgressIndicator()) : Padding(
        padding: const EdgeInsets.all(16),
        child: Card(child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Center(child: Icon(Icons.check_circle, color: Colors.green, size: 64)),
            const SizedBox(height: 16),
            Center(child: Text('₦${(_receipt['amount'] ?? 0).toStringAsFixed(2)}', style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold))),
            const Divider(height: 32),
            _row('Reference', _receipt['txRef'] ?? ''),
            _row('Type', _receipt['type'] ?? ''),
            _row('Status', _receipt['status'] ?? ''),
            _row('Date', _receipt['createdAt'] ?? ''),
            _row('Agent', _receipt['agentCode'] ?? ''),
            const SizedBox(height: 24),
            SizedBox(width: double.infinity, child: OutlinedButton.icon(
              onPressed: () {}, icon: const Icon(Icons.share), label: const Text('Share Receipt'),
            )),
          ]),
        )),
      ),
    );
  }

  Widget _row(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      Text(label, style: const TextStyle(color: Colors.grey)), Text(value, style: const TextStyle(fontWeight: FontWeight.w500)),
    ]),
  );
}
