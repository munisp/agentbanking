import 'package:flutter/material.dart';
import '../services/api_service.dart';


class MultiCurrencyScreen extends StatefulWidget {
  const MultiCurrencyScreen({super.key});
  @override
  State<MultiCurrencyScreen> createState() => _MultiCurrencyScreenState();
}

class _MultiCurrencyScreenState extends State<MultiCurrencyScreen> {
  static const _currencies = ['NGN', 'USD', 'GBP', 'EUR', 'GHS', 'KES', 'ZAR', 'XOF'];
  static const Map<String, double> _mockRates = {
    'NGN/USD': 0.000625, 'NGN/GBP': 0.000500, 'NGN/EUR': 0.000580,
    'NGN/GHS': 0.0075, 'NGN/KES': 0.0806, 'NGN/ZAR': 0.0113, 'NGN/XOF': 0.3750,
    'USD/NGN': 1600.0, 'GBP/NGN': 2000.0, 'EUR/NGN': 1724.0,
  };

  String _from = 'NGN';
  String _to = 'USD';
  String _amount = '1000';
  String _search = '';

  double _getRate(String from, String to) {
    if (from == to) return 1.0;
    return _mockRates['$from/$to'] ?? (1.0 / (_mockRates['$to/$from'] ?? 1.0));
  }

  List<MapEntry<String, double>> get _filteredRates => _mockRates.entries
      .where((e) => e.key.toLowerCase().contains(_search.toLowerCase()))
      .toList();

  @override
  Widget build(BuildContext context) {
    final rate = _getRate(_from, _to);
    final converted = (double.tryParse(_amount) ?? 0) * rate;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Multi-Currency')),
      body: RefreshIndicator(
        onRefresh: () async => setState(() {}),
        child: ListView(padding: const EdgeInsets.all(16), children: [
          // Converter Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Currency Converter', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 16),
                Row(children: [
                  Expanded(child: DropdownButtonFormField<String>(
                    value: _from,
                    items: _currencies.map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
                    onChanged: (v) => setState(() => _from = v!),
                    decoration: const InputDecoration(labelText: 'From'),
                  )),
                  const SizedBox(width: 12),
                  IconButton(
                    icon: const Icon(Icons.swap_horiz),
                    onPressed: () => setState(() { final tmp = _from; _from = _to; _to = tmp; }),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: DropdownButtonFormField<String>(
                    value: _to,
                    items: _currencies.where((c) => c != _from).map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
                    onChanged: (v) => setState(() => _to = v!),
                    decoration: const InputDecoration(labelText: 'To'),
                  )),
                ]),
                const SizedBox(height: 12),
                TextField(
                  decoration: const InputDecoration(labelText: 'Amount'),
                  keyboardType: TextInputType.number,
                  onChanged: (v) => setState(() => _amount = v),
                  controller: TextEditingController(text: _amount)..selection = TextSelection.collapsed(offset: _amount.length),
                ),
                const SizedBox(height: 12),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(children: [
                    Text('${converted.toStringAsFixed(2)} $_to',
                        style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: theme.colorScheme.primary)),
                    Text('Rate: 1 $_from = ${rate.toStringAsFixed(4)} $_to',
                        style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                  ]),
                ),
              ]),
            ),
          ),
          const SizedBox(height: 16),
          // Search
          TextField(
            decoration: const InputDecoration(hintText: 'Search rates...', prefixIcon: Icon(Icons.search)),
            onChanged: (v) => setState(() => _search = v),
          ),
          const SizedBox(height: 12),
          // Rate Table
          Card(
            child: DataTable(
              columns: const [
                DataColumn(label: Text('Pair')),
                DataColumn(label: Text('Rate'), numeric: true),
              ],
              rows: _filteredRates.map((e) => DataRow(cells: [
                DataCell(Text(e.key, style: const TextStyle(fontWeight: FontWeight.w600))),
                DataCell(Text(e.value.toStringAsFixed(4))),
              ])).toList(),
            ),
          ),
        ]),
      ),
    );
  }
}
