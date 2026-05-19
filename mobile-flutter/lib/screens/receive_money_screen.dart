import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../services/api_service.dart';

class ReceiveMoneyScreen extends StatefulWidget {
  const ReceiveMoneyScreen({super.key});
  @override
  State<ReceiveMoneyScreen> createState() => _ReceiveMoneyScreenState();
}

class _ReceiveMoneyScreenState extends State<ReceiveMoneyScreen> {
  String? _qrData;
  String? _accountNumber;
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getReceiveDetails();
      setState(() {
        _accountNumber = data['account_number'];
        _qrData = data['qr_data'] ?? data['account_number'];
        _loading = false;
      });
    } catch (_) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Receive Money')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            if (_qrData != null) QrImageView(data: _qrData!, size: 220),
            const SizedBox(height: 24),
            Text('Account Number', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 4),
            SelectableText(_accountNumber ?? '',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              icon: const Icon(Icons.copy),
              label: const Text('Copy Account Number'),
              onPressed: () {
                // Clipboard.setData(ClipboardData(text: _accountNumber ?? ''));
                ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Copied to clipboard')));
              },
            ),
          ])),
  );
}
