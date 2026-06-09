import 'package:flutter/material.dart';

class Bulk_transferScreen extends StatefulWidget {
  const Bulk_transferScreen({super.key});

  @override
  State<Bulk_transferScreen> createState() => _Bulk_transferScreenState();
}

class _Bulk_transferScreenState extends State<Bulk_transferScreen> {
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
      appBar: AppBar(title: const Text('bulk transfer')),
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
