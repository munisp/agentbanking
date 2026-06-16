import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ExchangeRatesScreen extends StatefulWidget {
  const ExchangeRatesScreen({super.key});
  @override
  State<ExchangeRatesScreen> createState() => _ExchangeRatesScreenState();
}

class _ExchangeRatesScreenState extends State<ExchangeRatesScreen> {
  List<Map<String, dynamic>> _rates = [];
  bool _loading = true;
  DateTime? _lastUpdated;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getExchangeRates();
      setState(() {
        _rates = List<Map<String, dynamic>>.from(data['rates'] ?? data);
        _lastUpdated = DateTime.now();
        _loading = false;
      });
    } catch (_) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Exchange Rates'),
      actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _load)],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : Column(children: [
            if (_lastUpdated != null)
              Padding(
                padding: const EdgeInsets.all(8),
                child: Text('Last updated: ${_lastUpdated.toString().split('.')[0]}',
                    style: const TextStyle(color: Colors.grey, fontSize: 12)),
              ),
            Expanded(child: ListView.separated(
              itemCount: _rates.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final r = _rates[i];
                return ListTile(
                  leading: CircleAvatar(
                    child: Text(r['currency'] ?? '', style: const TextStyle(fontSize: 10)),
                  ),
                  title: Text('${r['currency'] ?? ''} / NGN'),
                  subtitle: Text(r['source'] ?? 'CBN Rate'),
                  trailing: Text('₦${r['rate']?.toStringAsFixed(2) ?? '—'}',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                );
              },
            )),
          ]),
  );
}
