import 'package:flutter/material.dart';
import '../services/api_service.dart';

class AgentPerformanceScreen extends StatefulWidget {
  const AgentPerformanceScreen({super.key});
  @override
  State<AgentPerformanceScreen> createState() => _AgentPerformanceScreenState();
}

class _AgentPerformanceScreenState extends State<AgentPerformanceScreen> {
  List<dynamic> _agents = [];
  bool _loading = true;
  String _search = '';
  String _sortBy = 'points';
  final _sortOptions = ['points', 'volume', 'transactions'];

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getAgentLeaderboard(sortBy: _sortBy);
      setState(() { _agents = data['agents'] ?? []; _loading = false; });
    } catch (_) { setState(() => _loading = false); }
  }

  List<dynamic> get _filtered => _agents.where((a) {
    final q = _search.toLowerCase();
    return (a['name'] ?? '').toString().toLowerCase().contains(q) ||
           (a['agentCode'] ?? '').toString().toLowerCase().contains(q);
  }).toList();

  Color _tierColor(String tier) {
    switch (tier) {
      case 'Gold': return Colors.amber;
      case 'Silver': return Colors.grey.shade400;
      case 'Platinum': return Colors.blueGrey.shade200;
      default: return Colors.brown.shade300;
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = _agents.where((a) => (a['monthlyTxCount'] ?? 0) > 0).length;
    final avgScore = _agents.isEmpty ? 0 : (_agents.fold<int>(0, (s, a) => s + ((a['loyaltyPoints'] ?? 0) as int)) / _agents.length).round();
    final topPerformer = _agents.isNotEmpty ? _agents[0]['name'] ?? '—' : '—';

    return Scaffold(
      appBar: AppBar(title: const Text('Agent Performance')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: Column(children: [
                // KPI Row
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(children: [
                    _kpi('Total', '${_agents.length}'),
                    _kpi('Active', '$active'),
                    _kpi('Avg Score', '$avgScore'),
                  ]),
                ),
                // Search
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: TextField(
                    decoration: const InputDecoration(hintText: 'Search agents...', prefixIcon: Icon(Icons.search)),
                    onChanged: (v) => setState(() => _search = v),
                  ),
                ),
                // Sort chips
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(children: _sortOptions.map((o) => Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(o[0].toUpperCase() + o.substring(1)),
                      selected: _sortBy == o,
                      onSelected: (_) => setState(() { _sortBy = o; _load(); }),
                    ),
                  )).toList()),
                ),
                // Agent list
                Expanded(
                  child: ListView.builder(
                    itemCount: _filtered.length,
                    itemBuilder: (_, i) {
                      final a = _filtered[i];
                      return Card(
                        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: Theme.of(context).colorScheme.primary,
                            child: Text('#${i + 1}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                          ),
                          title: Row(children: [
                            Expanded(child: Text(a['name'] ?? '', style: const TextStyle(fontWeight: FontWeight.w600))),
                            Chip(
                              label: Text(a['tier'] ?? 'Bronze', style: const TextStyle(fontSize: 11, color: Colors.black87)),
                              backgroundColor: _tierColor(a['tier'] ?? 'Bronze'),
                              padding: EdgeInsets.zero,
                              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            ),
                          ]),
                          subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(a['agentCode'] ?? '', style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
                            const SizedBox(height: 4),
                            Row(children: [
                              Text('Tx: ${a['monthlyTxCount'] ?? 0}', style: const TextStyle(fontSize: 12)),
                              const SizedBox(width: 12),
                              Text('Vol: ₦${((a['monthlyVolume'] ?? 0) / 100).toStringAsFixed(0)}', style: const TextStyle(fontSize: 12)),
                              const SizedBox(width: 12),
                              Text('${a['loyaltyPoints'] ?? 0} pts', style: const TextStyle(fontSize: 12, color: Colors.amber, fontWeight: FontWeight.w600)),
                            ]),
                          ]),
                        ),
                      );
                    },
                  ),
                ),
              ]),
            ),
    );
  }

  Widget _kpi(String label, String value) => Expanded(
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(children: [
          Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          Text(label, style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
        ]),
      ),
    ),
  );
}
