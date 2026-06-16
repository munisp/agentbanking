import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../services/api_service.dart';


class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key});
  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen> {
  bool _scanned = false;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Scan QR Code')),
    body: MobileScanner(
      onDetect: (capture) {
        if (_scanned) return;
        final barcode = capture.barcodes.first;
        if (barcode.rawValue != null) {
          _scanned = true;
          Navigator.pop(context, barcode.rawValue);
        }
      },
    ),
  );
}
