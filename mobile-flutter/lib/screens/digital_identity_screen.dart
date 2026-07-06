import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';

class DigitalIdentityScreen extends ConsumerStatefulWidget {
  const DigitalIdentityScreen({super.key});

  @override
  ConsumerState<DigitalIdentityScreen> createState() => _DigitalIdentityScreenState();
}

class _DigitalIdentityScreenState extends ConsumerState<DigitalIdentityScreen> {
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
      final statsResp = await api.get('/api/trpc/digital_identity.getStats');
      final listResp = await api.get('/api/trpc/digital_identity.list?input={"limit":20,"offset":0}');
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

  Widget _buildVerificationLevel(Map<String, dynamic> item) {
    final level = int.tryParse('${item[\'verificationLevel\'] ?? 1}') ?? 1;
    return Row(children: List.generate(4, (i) => Container(width: 20, height: 6, margin: const EdgeInsets.only(right: 2), decoration: BoxDecoration(color: i < level ? Colors.green : Colors.grey[300], borderRadius: BorderRadius.circular(3)))));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final filtered = _searchQuery.isEmpty ? _items : _items.where((item) => item.values.any((v) => '$v'.toLowerCase().contains(_searchQuery.toLowerCase()))).toList();

    return Scaffold(
      appBar: AppBar(
        title: Row(children: [Icon(Icons.fingerprint, size: 24), const SizedBox(width: 8), const Text('Digital Identity Layer')]),
        actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _loadData)],
      ),
      body: _loading ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.error_outline, size: 48, color: theme.colorScheme.error), const SizedBox(height: 16),
              Text(_error, textAlign: TextAlign.center), const SizedBox(height: 16),
              ElevatedButton(onPressed: _loadData, child: const Text('Retry'))]))
          : RefreshIndicator(onRefresh: _loadData, child: CustomScrollView(slivers: [
              SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Digital Identity Layer', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('Decentralized identity, NIN enrollment & verification', style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey)),
              ]))),
              SliverPadding(padding: const EdgeInsets.symmetric(horizontal: 16),
                sliver: SliverGrid(gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 12, crossAxisSpacing: 12, childAspectRatio: 1.6),
                  delegate: SliverChildListDelegate([
                              _buildStatCard('Identities', '${_stats?['totalIdentities'] ?? '\u2014'}', Icons.person_pin, Colors.blue),
                              _buildStatCard('Verified Today', '${_stats?['verifiedToday'] ?? '\u2014'}', Icons.verified, Colors.green),
                              _buildStatCard('NIN Enrolled', '${_stats?['ninEnrollments'] ?? '\u2014'}', Icons.badge, Colors.orange),
                              _buildStatCard('Fraud Detected', '${_stats?['fraudDetected'] ?? '\u2014'}', Icons.gpp_bad, Colors.red),
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
                    title: Text('${item['fullName'] ?? item['dateOfBirth'] ?? item['nin'] ?? \'Record #${item[\'id\']}\'}', overflow: TextOverflow.ellipsis),
                    subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Status: ${item[\'status\'] ?? \'\u2014\'}', style: const TextStyle(fontSize: 12)),
                      const SizedBox(height: 4),
                      _buildVerificationLevel(item),
                    ]),
                    trailing: Icon(Icons.chevron_right, color: Colors.grey[400]), isThreeLine: true));
              }, childCount: filtered.length)),
              const SliverPadding(padding: EdgeInsets.only(bottom: 32)),
            ])),
    );
  }
}
