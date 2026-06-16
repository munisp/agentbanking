import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../services/api_client.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';


class RateCalculatorScreen extends ConsumerStatefulWidget {
  const RateCalculatorScreen({super.key});

  @override
  ConsumerState<RateCalculatorScreen> createState() => _RateCalculatorScreenState();
}

class _RateCalculatorScreenState extends ConsumerState<RateCalculatorScreen> {
  final _amountCtrl = TextEditingController();
  String _fromCurrency = 'NGN';
  String _toCurrency = 'USD';
  double? _convertedAmount;
  double? _exchangeRate;
  bool _isLoading = false;
  String? _error;

  static const List<String> _currencies = ['NGN', 'USD', 'GBP', 'EUR', 'GHS', 'KES', 'ZAR', 'XOF'];

  static const Map<String, String> _currencyFlags = {
    'NGN': '🇳🇬', 'USD': '🇺🇸', 'GBP': '🇬🇧', 'EUR': '🇪🇺',
    'GHS': '🇬🇭', 'KES': '🇰🇪', 'ZAR': '🇿🇦', 'XOF': '🌍',
  };

  Future<void> _calculate() async {
    final amount = double.tryParse(_amountCtrl.text.replaceAll(',', ''));
    if (amount == null || amount <= 0) {
      setState(() => _error = 'Please enter a valid amount');
      return;
    }
    setState(() { _isLoading = true; _error = null; });
    try {
      final auth = ref.read(authProvider);
      final response = await ApiClient.instance.get(
        '/api/trpc/management.getExchangeRates?input={}',
        token: auth.token,
      );
      final rates = response['result']?['data']?['rates'] as Map<String, dynamic>? ?? {};
      final fromRate = (rates[_fromCurrency] as num?)?.toDouble() ?? 1.0;
      final toRate = (rates[_toCurrency] as num?)?.toDouble() ?? 1.0;
      final rate = toRate / fromRate;
      setState(() {
        _exchangeRate = rate;
        _convertedAmount = amount * rate;
      });
    } catch (e) {
      // Fallback to static rates for offline use
      final staticRates = {'NGN': 1.0, 'USD': 0.00065, 'GBP': 0.00052, 'EUR': 0.00060, 'GHS': 0.0078, 'KES': 0.083, 'ZAR': 0.012, 'XOF': 0.39};
      final fromRate = staticRates[_fromCurrency] ?? 1.0;
      final toRate = staticRates[_toCurrency] ?? 1.0;
      final rate = toRate / fromRate;
      setState(() {
        _exchangeRate = rate;
        _convertedAmount = amount * rate;
        _error = 'Using offline rates (last updated)';
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _swapCurrencies() {
    setState(() {
      final temp = _fromCurrency;
      _fromCurrency = _toCurrency;
      _toCurrency = temp;
      _convertedAmount = null;
      _exchangeRate = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Rate Calculator', style: TextStyle(color: Colors.white)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => context.go('/dashboard'),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Currency Converter', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            const Text('Real-time exchange rates for 54Link transactions', style: TextStyle(color: Color(0xFF94A3B8))),
            const SizedBox(height: 32),
            // Amount input
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Amount', style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _amountCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
                    decoration: const InputDecoration(
                      border: InputBorder.none,
                      hintText: '0.00',
                      hintStyle: TextStyle(color: Color(0xFF475569)),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            // Currency selectors
            Row(
              children: [
                Expanded(child: _buildCurrencySelector('From', _fromCurrency, (v) => setState(() { _fromCurrency = v; _convertedAmount = null; }))),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: GestureDetector(
                    onTap: _swapCurrencies,
                    child: Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: const Color(0xFF1A56DB),
                        borderRadius: BorderRadius.circular(22),
                      ),
                      child: const Icon(Icons.swap_horiz, color: Colors.white),
                    ),
                  ),
                ),
                Expanded(child: _buildCurrencySelector('To', _toCurrency, (v) => setState(() { _toCurrency = v; _convertedAmount = null; }))),
              ],
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isLoading ? null : _calculate,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1A56DB),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: _isLoading
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Calculate', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.orange, fontSize: 12)),
            ],
            if (_convertedAmount != null) ...[
              const SizedBox(height: 24),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: const Color(0xFF1E293B),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFF1A56DB).withOpacity(0.4)),
                ),
                child: Column(
                  children: [
                    Text(
                      '${_currencyFlags[_fromCurrency] ?? ''} ${_amountCtrl.text} $_fromCurrency',
                      style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 16),
                    ),
                    const SizedBox(height: 8),
                    const Icon(Icons.arrow_downward, color: Color(0xFF1A56DB)),
                    const SizedBox(height: 8),
                    Text(
                      '${_currencyFlags[_toCurrency] ?? ''} ${_convertedAmount!.toStringAsFixed(4)} $_toCurrency',
                      style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Rate: 1 $_fromCurrency = ${_exchangeRate!.toStringAsFixed(6)} $_toCurrency',
                      style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildCurrencySelector(String label, String selected, ValueChanged<String> onChanged) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
          const SizedBox(height: 4),
          DropdownButton<String>(
            value: selected,
            isExpanded: true,
            dropdownColor: const Color(0xFF1E293B),
            style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            underline: const SizedBox(),
            items: _currencies.map((c) => DropdownMenuItem(
              value: c,
              child: Text('${_currencyFlags[c] ?? ''} $c'),
            )).toList(),
            onChanged: (v) { if (v != null) onChanged(v); },
          ),
        ],
      ),
    );
  }
}
