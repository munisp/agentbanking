import 'package:flutter/material.dart';

class Utility_billsScreen extends StatefulWidget {
  const Utility_billsScreen({super.key});

  @override
  State<Utility_billsScreen> createState() => _Utility_billsScreenState();
}

class _Utility_billsScreenState extends State<Utility_billsScreen> {
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
      appBar: AppBar(title: const Text('utility bills')),
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
