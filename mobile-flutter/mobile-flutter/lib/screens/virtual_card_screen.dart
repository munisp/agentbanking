import 'package:flutter/material.dart';
import '../services/api_service.dart';

class VirtualCardScreen extends StatefulWidget {
  const VirtualCardScreen({super.key});
  @override
  State<VirtualCardScreen> createState() => _VirtualCardScreenState();
}

class _VirtualCardScreenState extends State<VirtualCardScreen> {
  Map<String, dynamic>? _card;
  bool _loading = true;
  bool _detailsVisible = false;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getVirtualCard();
      setState(() { _card = data; _loading = false; });
    } catch (_) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Virtual Card')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _card == null
            ? Center(child: ElevatedButton(
                onPressed: () async {
                  setState(() => _loading = true);
                  try {
                    await ApiService.instance.createVirtualCard();
                    await _load();
                  } catch (e) {
                    setState(() => _loading = false);
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
                  }
                },
                child: const Text('Create Virtual Card')))
            : Padding(
                padding: const EdgeInsets.all(16),
                child: Column(children: [
                  Container(
                    width: double.infinity,
                    height: 200,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                          colors: [Color(0xFF1a1a2e), Color(0xFF16213e)]),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    padding: const EdgeInsets.all(20),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('54Link Virtual Card',
                          style: TextStyle(color: Colors.white70, fontSize: 12)),
                      const Spacer(),
                      Text(_detailsVisible
                          ? _card!['card_number'] ?? '•••• •••• •••• ••••'
                          : '•••• •••• •••• ${(_card!['last4'] ?? '••••')}',
                          style: const TextStyle(color: Colors.white, fontSize: 20,
                              letterSpacing: 2)),
                      const SizedBox(height: 8),
                      Row(children: [
                        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          const Text('EXPIRES', style: TextStyle(color: Colors.white54, fontSize: 10)),
                          Text(_card!['expiry'] ?? '••/••',
                              style: const TextStyle(color: Colors.white)),
                        ]),
                        const SizedBox(width: 24),
                        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          const Text('CVV', style: TextStyle(color: Colors.white54, fontSize: 10)),
                          Text(_detailsVisible ? (_card!['cvv'] ?? '•••') : '•••',
                              style: const TextStyle(color: Colors.white)),
                        ]),
                      ]),
                    ]),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    icon: Icon(_detailsVisible ? Icons.visibility_off : Icons.visibility),
                    label: Text(_detailsVisible ? 'Hide Details' : 'Show Details'),
                    onPressed: () => setState(() => _detailsVisible = !_detailsVisible),
                  ),
                ]),
              ),
  );
}
