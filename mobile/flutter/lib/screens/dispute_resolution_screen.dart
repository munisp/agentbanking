import 'package:flutter/material.dart';

class DisputeResolutionScreen extends StatefulWidget {
  const DisputeResolutionScreen({super.key});

  @override
  State<DisputeResolutionScreen> createState() => _DisputeResolutionScreenState();
}

class _DisputeResolutionScreenState extends State<DisputeResolutionScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _disputes = [];

  @override
  void initState() {
    super.initState();
    _loadDisputes();
  }

  Future<void> _loadDisputes() async {
    setState(() => _isLoading = true);
    await Future.delayed(const Duration(seconds: 1));
    setState(() {
      _disputes = [
        {'id': 'DSP-001', 'type': 'Failed Transaction', 'amount': 5000, 'status': 'open', 'date': '2024-01-15'},
        {'id': 'DSP-002', 'type': 'Wrong Amount', 'amount': 12000, 'status': 'investigating', 'date': '2024-01-14'},
        {'id': 'DSP-003', 'type': 'Duplicate Charge', 'amount': 3500, 'status': 'resolved', 'date': '2024-01-12'},
      ];
      _isLoading = false;
    });
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'open': return Colors.orange;
      case 'investigating': return Colors.blue;
      case 'resolved': return Colors.green;
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dispute Resolution')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _disputes.isEmpty
              ? const Center(child: Text('No disputes found'))
              : RefreshIndicator(
                  onRefresh: _loadDisputes,
                  child: ListView.builder(
                    itemCount: _disputes.length,
                    itemBuilder: (context, index) {
                      final d = _disputes[index];
                      return Card(
                        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        child: ListTile(
                          title: Text(d['type']),
                          subtitle: Text('${d['id']} • ${d['date']}'),
                          trailing: Chip(
                            label: Text(d['status'].toUpperCase(), style: const TextStyle(fontSize: 10)),
                            backgroundColor: _statusColor(d['status']).withOpacity(0.2),
                          ),
                          onTap: () {},
                        ),
                      );
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {},
        icon: const Icon(Icons.add),
        label: const Text('New Dispute'),
      ),
    );
  }
}
