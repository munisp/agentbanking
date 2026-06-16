import 'package:flutter/material.dart';
import '../services/api_service.dart';

class AirtimeVendingScreen extends StatefulWidget {
  const AirtimeVendingScreen({super.key});
  @override
  State<AirtimeVendingScreen> createState() => _AirtimeVendingScreenState();
}

class _AirtimeVendingScreenState extends State<AirtimeVendingScreen> {
  Map<String, dynamic> _data = {};
  List<dynamic> _items = [];
  bool _loading = true;
  String _error = '';
  String _search = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await ApiService.instance.get('/airtime/list', queryParams: {'page': '1', 'limit': '50'});
      setState(() {
        _data = result ?? {};
        _items = result['items'] ?? result['data'] ?? [];
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  List<dynamic> get _filtered => _items.where((item) {
    if (_search.isEmpty) return true;
    final q = _search.toLowerCase();
    return (item['name'] ?? item['title'] ?? item['id'] ?? '').toString().toLowerCase().contains(q);
  }).toList();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Airtime Vending'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () { setState(() => _loading = true); _load(); }),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  const SizedBox(height: 8),
                  Text(_error, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  ElevatedButton(onPressed: () { setState(() { _error = ''; _loading = true; }); _load(); }, child: const Text('Retry')),
                ]))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: Column(children: [
                    // Search bar
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: TextField(
                        decoration: InputDecoration(
                          hintText: 'Search...',
                          prefixIcon: const Icon(Icons.search),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                        ),
                        onChanged: (v) => setState(() => _search = v),
                      ),
                    ),
                    // Summary cards
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Row(children: [
                        _summaryCard('Total', _items.length.toString(), Colors.blue),
                        const SizedBox(width: 8),
                        _summaryCard('Filtered', _filtered.length.toString(), Colors.green),
                      ]),
                    ),
                    const SizedBox(height: 8),
                    // List
                    Expanded(
                      child: _filtered.isEmpty
                          ? const Center(child: Text('No items found'))
                          : ListView.builder(
                              itemCount: _filtered.length,
                              itemBuilder: (ctx, i) {
                                final item = _filtered[i];
                                return Card(
                                  margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                  child: ListTile(
                                    leading: CircleAvatar(child: Text('${i + 1}')),
                                    title: Text(item['name'] ?? item['title'] ?? item['id']?.toString() ?? 'Item ${i + 1}'),
                                    subtitle: Text(item['status'] ?? item['type'] ?? ''),
                                    trailing: const Icon(Icons.chevron_right),
                                    onTap: () {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        SnackBar(content: Text('Selected: ${item['name'] ?? item['id']}')),
                                      );
                                    },
                                  ),
                                );
                              },
                            ),
                    ),
                  ]),
                ),
    );
  }

  Widget _summaryCard(String label, String value, Color color) {
    return Expanded(
      child: Card(
        color: color.withOpacity(0.1),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(children: [
            Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
            Text(label, style: TextStyle(color: color.withOpacity(0.8))),
          ]),
        ),
      ),
    );
  }
}
