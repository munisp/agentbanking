import 'package:flutter/material.dart';
import '../services/api_service.dart';

class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key});
  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen> {
  bool _scanning = true;
  String? _scannedData;

  Future<void> _processQrCode(String data) async {
    setState(() { _scanning = false; _scannedData = data; });
    try {
      final result = await ApiService.post('/qr-payments/process', {'qrData': data});
      if (mounted) {
        showDialog(context: context, builder: (_) => AlertDialog(
          title: const Text('Payment Details'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('Merchant: ${result['merchantName'] ?? 'Unknown'}'),
            Text('Amount: ₦${(result['amount'] ?? 0).toStringAsFixed(2)}'),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            TextButton(onPressed: () { Navigator.pop(context); _confirmPayment(result); }, child: const Text('Pay')),
          ],
        ));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Invalid QR: $e')));
      setState(() => _scanning = true);
    }
  }

  Future<void> _confirmPayment(Map<String, dynamic> details) async {
    try {
      await ApiService.post('/qr-payments/confirm', details);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Payment successful')));
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Payment failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan QR Code')),
      body: Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Container(
          width: 280, height: 280,
          decoration: BoxDecoration(border: Border.all(color: Colors.blue, width: 3), borderRadius: BorderRadius.circular(16)),
          child: _scanning
            ? const Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Icon(Icons.qr_code_scanner, size: 80, color: Colors.blue),
                SizedBox(height: 16),
                Text('Point camera at QR code', style: TextStyle(color: Colors.grey)),
              ])
            : Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.check, size: 60, color: Colors.green),
                Text(_scannedData ?? '', maxLines: 2, overflow: TextOverflow.ellipsis),
              ]),
        ),
        const SizedBox(height: 32),
        if (!_scanning) ElevatedButton(onPressed: () => setState(() => _scanning = true), child: const Text('Scan Again')),
      ])),
    );
  }
}
