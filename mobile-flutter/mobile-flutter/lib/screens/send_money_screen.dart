import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/primary_button.dart';

class SendMoneyScreen extends StatefulWidget {
  const SendMoneyScreen({super.key});
  @override
  State<SendMoneyScreen> createState() => _SendMoneyScreenState();
}

class _SendMoneyScreenState extends State<SendMoneyScreen> {
  final _recipientCtrl = TextEditingController();
  final _amountCtrl = TextEditingController();
  final _narrationCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  Future<void> _send() async {
    final amount = double.tryParse(_amountCtrl.text.replaceAll(',', ''));
    if (amount == null || amount <= 0) {
      setState(() => _error = 'Enter a valid amount');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      await ApiService.instance.sendMoney(
        recipient: _recipientCtrl.text.trim(),
        amount: amount,
        narration: _narrationCtrl.text.trim(),
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Transfer initiated successfully')));
        Navigator.pop(context);
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _recipientCtrl.dispose(); _amountCtrl.dispose(); _narrationCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Send Money')),
    body: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextField(controller: _recipientCtrl,
            decoration: const InputDecoration(labelText: 'Phone / Account Number',
                prefixIcon: Icon(Icons.person))),
        const SizedBox(height: 12),
        TextField(controller: _amountCtrl,
            decoration: const InputDecoration(labelText: 'Amount (NGN)',
                prefixIcon: Icon(Icons.attach_money)),
            keyboardType: const TextInputType.numberWithOptions(decimal: true)),
        const SizedBox(height: 12),
        TextField(controller: _narrationCtrl,
            decoration: const InputDecoration(labelText: 'Narration (optional)')),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: const TextStyle(color: Colors.red)),
        ],
        const Spacer(),
        PrimaryButton(label: 'Send Money', onPressed: _loading ? null : _send,
            loading: _loading),
      ]),
    ),
  );
}
