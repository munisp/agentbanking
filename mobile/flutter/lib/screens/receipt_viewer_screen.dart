import 'package:flutter/material.dart';

class Receipt_viewerScreen extends StatefulWidget {
  const Receipt_viewerScreen({super.key});

  @override
  State<Receipt_viewerScreen> createState() => _Receipt_viewerScreenState();
}

class _Receipt_viewerScreenState extends State<Receipt_viewerScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _items = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    await Future.delayed(const Duration(seconds: 1));
    setState(() {
      _items = List.generate(10, (i) => {'id': i, 'title': 'Item ${i + 1}'});
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('receipt viewer')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? const Center(child: Text('No data available'))
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: ListView.builder(
                    itemCount: _items.length,
                    itemBuilder: (context, index) {
                      final item = _items[index];
                      return ListTile(
                        title: Text(item['title']),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {},
                      );
                    },
                  ),
                ),
    );
  }
}
