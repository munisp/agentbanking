import 'package:flutter/material.dart';
import '../services/api_service.dart';

class CashOutScreen extends StatefulWidget {
  const CashOutScreen({super.key});
  @override
  State<CashOutScreen> createState() => _CashOutScreenState();
}

class _CashOutScreenState extends State<CashOutScreen> {
  final _formKey = GlobalKey<FormState>();
  double _amount = 0;
  String _customerPhone = '';
  String _pin = '';
  bool _loading = false;

  Future<void> _processCashOut() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();
    setState(() => _loading = true);
    try {
      final result = await ApiService.post('/cash-out/create', {
        'amount': _amount, 'customerPhone': _customerPhone, 'pin': _pin, 'channel': 'mobile',
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Cash-out successful: ${result['txRef']}')));
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Cash-out failed: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cash Out')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(children: [
            TextFormField(
              decoration: const InputDecoration(labelText: 'Customer Phone', prefixText: '+234 '),
              keyboardType: TextInputType.phone,
              onSaved: (v) => _customerPhone = v ?? '',
              validator: (v) => v == null || v.length < 10 ? 'Enter valid phone' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              decoration: const InputDecoration(labelText: 'Amount (NGN)', prefixText: '₦ '),
              keyboardType: TextInputType.number,
              onSaved: (v) => _amount = double.tryParse(v ?? '0') ?? 0,
              validator: (v) { final n = double.tryParse(v ?? ''); return n == null || n <= 0 ? 'Enter valid amount' : null; },
            ),
            const SizedBox(height: 16),
            TextFormField(
              decoration: const InputDecoration(labelText: 'PIN'),
              obscureText: true, maxLength: 4,
              onSaved: (v) => _pin = v ?? '',
              validator: (v) => v == null || v.length != 4 ? 'Enter 4-digit PIN' : null,
            ),
            const SizedBox(height: 24),
            SizedBox(width: double.infinity, child: ElevatedButton(
              onPressed: _loading ? null : _processCashOut,
              child: _loading ? const CircularProgressIndicator() : const Text('Process Cash Out'),
            )),
          ]),
        ),
      ),
    );
  }
}
