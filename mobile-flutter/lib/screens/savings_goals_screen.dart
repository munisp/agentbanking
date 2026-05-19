import 'package:flutter/material.dart';
import '../services/api_service.dart';

class SavingsGoalsScreen extends StatefulWidget {
  const SavingsGoalsScreen({super.key});
  @override
  State<SavingsGoalsScreen> createState() => _SavingsGoalsScreenState();
}

class _SavingsGoalsScreenState extends State<SavingsGoalsScreen> {
  List<Map<String, dynamic>> _goals = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getSavingsGoals();
      setState(() { _goals = List<Map<String, dynamic>>.from(data); _loading = false; });
    } catch (_) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Savings Goals'),
      actions: [IconButton(icon: const Icon(Icons.add),
          onPressed: () => Navigator.pushNamed(context, '/create-savings-goal'))],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _goals.isEmpty
            ? const Center(child: Text('No savings goals yet. Create one!'))
            : ListView.builder(
                itemCount: _goals.length,
                itemBuilder: (_, i) {
                  final g = _goals[i];
                  final target = (g['target_amount'] ?? 0) / 100.0;
                  final current = (g['current_amount'] ?? 0) / 100.0;
                  final progress = target > 0 ? (current / target).clamp(0.0, 1.0) : 0.0;
                  return Card(
                    margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(g['name'] ?? '', style: const TextStyle(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        LinearProgressIndicator(value: progress),
                        const SizedBox(height: 4),
                        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                          Text('₦${current.toStringAsFixed(2)}'),
                          Text('₦${target.toStringAsFixed(2)}'),
                        ]),
                      ]),
                    ),
                  );
                }),
  );
}
