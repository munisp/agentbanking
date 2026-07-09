import 'package:flutter/material.dart';
import '../services/api_service.dart';

class EcommerceOrderManagementScreen extends StatefulWidget {
  const EcommerceOrderManagementScreen({super.key});
  @override
  State<EcommerceOrderManagementScreen> createState() => _EcommerceOrderManagementScreenState();
}

class _EcommerceOrderManagementScreenState extends State<EcommerceOrderManagementScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<dynamic> _orders = [];
  bool _loading = true;
  String _error = '';
  String _statusFilter = 'all';

  static const _statuses = ['all', 'pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled'];
  static const _statusIcons = {
    'pending': Icons.hourglass_empty,
    'confirmed': Icons.check_circle_outline,
    'processing': Icons.settings,
    'shipped': Icons.local_shipping,
    'delivered': Icons.done_all,
    'cancelled': Icons.cancel,
  };
  static const _statusColors = {
    'pending': Colors.orange,
    'confirmed': Colors.blue,
    'processing': Colors.purple,
    'shipped': Colors.indigo,
    'delivered': Colors.green,
    'cancelled': Colors.red,
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _statuses.length, vsync: this);
    _tabController.addListener(() { setState(() => _statusFilter = _statuses[_tabController.index]); });
    _loadOrders();
  }

  Future<void> _loadOrders() async {
    try {
      final result = await ApiService.instance.get('/ecommerceOrders/listOrders', queryParams: {'customerId': '1', 'limit': '50'});
      setState(() { _orders = result?['orders'] ?? []; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  List<dynamic> get _filtered => _statusFilter == 'all' ? _orders : _orders.where((o) => o['status'] == _statusFilter).toList();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Orders'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: _statuses.map((s) => Tab(text: s == 'all' ? 'All' : s[0].toUpperCase() + s.substring(1))).toList(),
        ),
        actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: () { setState(() => _loading = true); _loadOrders(); })],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  Text(_error, textAlign: TextAlign.center),
                  ElevatedButton(onPressed: () { setState(() { _error = ''; _loading = true; }); _loadOrders(); }, child: const Text('Retry')),
                ]))
              : RefreshIndicator(
                  onRefresh: _loadOrders,
                  child: _filtered.isEmpty
                      ? const Center(child: Text('No orders found'))
                      : ListView.builder(
                          padding: const EdgeInsets.all(8),
                          itemCount: _filtered.length,
                          itemBuilder: (ctx, i) {
                            final order = _filtered[i];
                            final status = order['status'] ?? 'pending';
                            final total = order['totalAmount'] ?? order['total'] ?? '0';
                            final date = order['createdAt'] ?? '';
                            final items = order['items'] as List? ?? [];
                            return Card(
                              margin: const EdgeInsets.symmetric(vertical: 4),
                              child: ExpansionTile(
                                leading: Icon(_statusIcons[status] ?? Icons.receipt, color: _statusColors[status] ?? Colors.grey),
                                title: Text('Order #${order['orderNumber'] ?? order['id']}', style: const TextStyle(fontWeight: FontWeight.bold)),
                                subtitle: Row(children: [
                                  Chip(label: Text(status, style: const TextStyle(fontSize: 11, color: Colors.white)), backgroundColor: _statusColors[status] ?? Colors.grey, padding: EdgeInsets.zero, materialTapTargetSize: MaterialTapTargetSize.shrinkWrap),
                                  const SizedBox(width: 8),
                                  Text('NGN $total', style: const TextStyle(fontWeight: FontWeight.w600)),
                                ]),
                                trailing: Text(_formatDate(date), style: const TextStyle(fontSize: 11, color: Colors.grey)),
                                children: [
                                  if (items.isNotEmpty) ...items.map((item) => ListTile(
                                    dense: true,
                                    title: Text(item['name'] ?? item['sku'] ?? '', style: const TextStyle(fontSize: 13)),
                                    subtitle: Text('Qty: ${item['quantity']} x NGN ${item['unitPrice']}'),
                                    trailing: Text('NGN ${((item['quantity'] ?? 1) * (double.tryParse(item['unitPrice']?.toString() ?? '0') ?? 0)).toStringAsFixed(2)}'),
                                  )),
                                  if (status == 'shipped') Padding(
                                    padding: const EdgeInsets.all(12),
                                    child: ElevatedButton.icon(
                                      onPressed: () {},
                                      icon: const Icon(Icons.location_on),
                                      label: const Text('Track Delivery'),
                                    ),
                                  ),
                                  if (status == 'delivered') Padding(
                                    padding: const EdgeInsets.all(12),
                                    child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                                      ElevatedButton.icon(onPressed: () {}, icon: const Icon(Icons.replay), label: const Text('Reorder')),
                                      OutlinedButton.icon(onPressed: () {}, icon: const Icon(Icons.star_border), label: const Text('Review')),
                                    ]),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                ),
    );
  }

  String _formatDate(String date) {
    try {
      final d = DateTime.parse(date);
      return '${d.day}/${d.month}/${d.year}';
    } catch (_) {
      return date.length > 10 ? date.substring(0, 10) : date;
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }
}
