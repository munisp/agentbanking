import 'package:flutter/material.dart';
import '../services/api_service.dart';

class BillPaymentScreen extends StatefulWidget {
  const BillPaymentScreen({super.key});
  @override
  State<BillPaymentScreen> createState() => _BillPaymentScreenState();
}

class _BillPaymentScreenState extends State<BillPaymentScreen> {
  final _formKey = GlobalKey<FormState>();
  String _billerId = '';
  String _customerRef = '';
  double _amount = 0;
  bool _loading = false;
  List<Map<String, dynamic>> _billers = [];

  @override
  void initState() {
    super.initState();
    _loadBillers();
  }

  Future<void> _loadBillers() async {
    setState(() => _loading = true);
    try {
      final data = await ApiService.get('/billers/list?page=1&limit=50');
      setState(() => _billers = List<Map<String, dynamic>>.from(data['items'] ?? []));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to load billers: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _validateBill() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();
    setState(() => _loading = true);
    try {
      final result = await ApiService.post('/bill-payments/validate', {
        'billerId': _billerId, 'customerRef': _customerRef, 'amount': _amount,
      });
      if (mounted) {
        showDialog(context: context, builder: (_) => AlertDialog(
          title: const Text('Bill Validated'),
          content: Text('Customer: ${result['customerName']}\nAmount: NGN ${_amount.toStringAsFixed(2)}'),
          actions: [
            TextButton(onPressed: () { Navigator.pop(context); _payBill(); }, child: const Text('Pay Now')),
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ],
        ));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Validation failed: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _payBill() async {
    setState(() => _loading = true);
    try {
      await ApiService.post('/bill-payments/pay', {
        'billerId': _billerId, 'customerRef': _customerRef, 'amount': _amount,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payment successful')));
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Payment failed: $e')));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Bill Payment')),
      body: _loading ? const Center(child: CircularProgressIndicator()) : Padding(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: ListView(children: [
            DropdownButtonFormField<String>(
              decoration: const InputDecoration(labelText: 'Biller'),
              items: _billers.map((b) => DropdownMenuItem(value: b['id']?.toString() ?? '', child: Text(b['name'] ?? 'Unknown'))).toList(),
              onChanged: (v) => _billerId = v ?? '',
              validator: (v) => v == null || v.isEmpty ? 'Select a biller' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              decoration: const InputDecoration(labelText: 'Customer Reference', hintText: 'Meter number / Account ID'),
              onSaved: (v) => _customerRef = v ?? '',
              validator: (v) => v == null || v.isEmpty ? 'Enter reference' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              decoration: const InputDecoration(labelText: 'Amount (NGN)', prefixText: '₦ '),
              keyboardType: TextInputType.number,
              onSaved: (v) => _amount = double.tryParse(v ?? '0') ?? 0,
              validator: (v) { final n = double.tryParse(v ?? ''); return n == null || n <= 0 ? 'Enter valid amount' : null; },
            ),
            const SizedBox(height: 24),
            ElevatedButton(onPressed: _validateBill, child: const Text('Validate & Pay')),
          ]),
        ),
      ),
    );
  }
}
