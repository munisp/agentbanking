import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ReceiptScreen extends StatefulWidget {
  const ReceiptScreen({super.key});
  @override
  State<ReceiptScreen> createState() => _ReceiptScreenState();
}

class _ReceiptScreenState extends State<ReceiptScreen> {
  Map<String, dynamic> _data = {};
  List<dynamic> _items = [];
  bool _loading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await ApiService.instance.get('/api/trpc/receipt.list', queryParams: {'page': '1', 'limit': '50'});
      setState(() {
        _data = result ?? {};
        _items = result['items'] ?? result['data'] ?? result['result']?['data'] ?? [];
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Receipt')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Text(_error, style: const TextStyle(color: Colors.red)))
              : _items.isEmpty
                  ? const Center(child: Text('No data available'))
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
                        itemCount: _items.length,
                        itemBuilder: (context, index) {
                          final item = _items[index];
                          return Card(
                            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                            child: ListTile(
                              title: Text(item['name'] ?? item['ref'] ?? item['id']?.toString() ?? 'Item ${index + 1}'),
                              subtitle: Text(item['status'] ?? item['type'] ?? item['description'] ?? ''),
                              trailing: item['amount'] != null
                                  ? Text('₦${item['amount']}', style: const TextStyle(fontWeight: FontWeight.bold))
                                  : null,
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
