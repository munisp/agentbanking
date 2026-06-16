import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ReferralScreen extends StatefulWidget {
  const ReferralScreen({super.key});
  @override
  State<ReferralScreen> createState() => _ReferralScreenState();
}

class _ReferralScreenState extends State<ReferralScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getReferralInfo();
      setState(() { _data = data; _loading = false; });
    } catch (_) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final code = _data?['referral_code'] ?? '';
    final earnings = (_data?['total_earnings'] ?? 0) / 100.0;
    final count = _data?['referral_count'] ?? 0;

    return Scaffold(
      appBar: AppBar(title: const Text('Refer & Earn')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Card(child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(children: [
                    const Text('Your Referral Code',
                        style: TextStyle(color: Colors.grey)),
                    const SizedBox(height: 8),
                    Text(code, style: const TextStyle(
                        fontSize: 28, fontWeight: FontWeight.bold,
                        letterSpacing: 4)),
                    const SizedBox(height: 12),
                    ElevatedButton.icon(
                      icon: const Icon(Icons.share),
                      label: const Text('Share Code'),
                      onPressed: () {/* Share.share('Join 54Link: $code') */},
                    ),
                  ]),
                )),
                const SizedBox(height: 16),
                Row(children: [
                  Expanded(child: _StatCard(label: 'Referrals', value: '$count')),
                  const SizedBox(width: 12),
                  Expanded(child: _StatCard(label: 'Earnings', value: '₦${earnings.toStringAsFixed(2)}')),
                ]),
              ]),
            ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  const _StatCard({required this.label, required this.value});
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        Text(value, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
        Text(label, style: const TextStyle(color: Colors.grey)),
      ]),
    ),
  );
}
