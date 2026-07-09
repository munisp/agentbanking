import 'package:flutter/material.dart';
import '../services/api_service.dart';

class CashInScreen extends StatefulWidget {
  const CashInScreen({super.key});
  @override
  State<CashInScreen> createState() => _CashInScreenState();
}

class _CashInScreenState extends State<CashInScreen> {
  final _formKey = GlobalKey<FormState>();
  double _amount = 0;
  String _customerPhone = '';
  bool _loading = false;

  Future<void> _processCashIn() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();
    setState(() => _loading = true);
    try {
      final result = await ApiService.post('/cash-in/create', {
        'amount': _amount, 'customerPhone': _customerPhone, 'channel': 'mobile',
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Cash-in successful: ${result['txRef']}')));
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Cash-in failed: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cash In')),
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
            const SizedBox(height: 24),
            SizedBox(width: double.infinity, child: ElevatedButton(
              onPressed: _loading ? null : _processCashIn,
              child: _loading ? const CircularProgressIndicator() : const Text('Process Cash In'),
            )),
          ]),
        ),
      ),
    );
  }
}
