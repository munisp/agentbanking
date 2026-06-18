import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';

class HealthInsuranceScreen extends ConsumerStatefulWidget {
  const HealthInsuranceScreen({super.key});

  @override
  ConsumerState<HealthInsuranceScreen> createState() => _HealthInsuranceScreenState();
}

class _HealthInsuranceScreenState extends ConsumerState<HealthInsuranceScreen> {
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
      final statsResp = await api.get('/api/trpc/health_insurance.getStats');
      final listResp = await api.get('/api/trpc/health_insurance.list?input={"limit":20,"offset":0}');
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

  Widget _buildClaimStatus(Map<String, dynamic> item) {
    final status = '${item[\'status\'] ?? \'active\'}';
    final ic = {'active': Icons.check_circle, 'claim_pending': Icons.hourglass_top, 'claim_paid': Icons.monetization_on, 'expired': Icons.cancel};
    final cc = {'active': Colors.green, 'claim_pending': Colors.orange, 'claim_paid': Colors.blue, 'expired': Colors.grey};
    return Row(mainAxisSize: MainAxisSize.min, children: [Icon(ic[status] ?? Icons.info, size: 16, color: cc[status] ?? Colors.grey), const SizedBox(width: 4), Text(status.replaceAll('_', ' '), style: TextStyle(fontSize: 11, color: cc[status] ?? Colors.grey))]);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final filtered = _searchQuery.isEmpty ? _items : _items.where((item) => item.values.any((v) => '$v'.toLowerCase().contains(_searchQuery.toLowerCase()))).toList();

    return Scaffold(
      appBar: AppBar(
        title: Row(children: [Icon(Icons.health_and_safety, size: 24), const SizedBox(width: 8), const Text('Health Insurance Micro')]),
        actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _loadData)],
      ),
      body: _loading ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.error_outline, size: 48, color: theme.colorScheme.error), const SizedBox(height: 16),
              Text(_error, textAlign: TextAlign.center), const SizedBox(height: 16),
              ElevatedButton(onPressed: _loadData, child: const Text('Retry'))]))
          : RefreshIndicator(onRefresh: _loadData, child: CustomScrollView(slivers: [
              SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Health Insurance Micro', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('Community-based health insurance for agents', style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey)),
              ]))),
              SliverPadding(padding: const EdgeInsets.symmetric(horizontal: 16),
                sliver: SliverGrid(gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 12, crossAxisSpacing: 12, childAspectRatio: 1.6),
                  delegate: SliverChildListDelegate([
                              _buildStatCard('Active Policies', '${_stats?['activePolicies'] ?? '\u2014'}', Icons.verified_user, Colors.blue),
                              _buildStatCard('Total Premiums', '₦${_stats?['totalPremiums'] ?? '\u2014'}', Icons.attach_money, Colors.green),
                              _buildStatCard('Pending Claims', '${_stats?['pendingClaims'] ?? '\u2014'}', Icons.pending, Colors.orange),
                              _buildStatCard('Claims Ratio', '${_stats?['claimRatio'] ?? '\u2014'}', Icons.pie_chart, Colors.purple),
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
                    title: Text('${item['holderName'] ?? item['planType'] ?? item['premium'] ?? \'Record #${item[\'id\']}\'}', overflow: TextOverflow.ellipsis),
                    subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Status: ${item[\'status\'] ?? \'\u2014\'}', style: const TextStyle(fontSize: 12)),
                      const SizedBox(height: 4),
                      _buildClaimStatus(item),
                    ]),
                    trailing: Icon(Icons.chevron_right, color: Colors.grey[400]), isThreeLine: true));
              }, childCount: filtered.length)),
              const SliverPadding(padding: EdgeInsets.only(bottom: 32)),
            ])),
    );
  }
}
