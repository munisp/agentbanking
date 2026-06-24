/// Bluetooth Thermal Printer Service
/// Supports: Sunmi, PAX, and generic ESC/POS Bluetooth printers.
/// Used for printing transaction receipts for customers.

import 'dart:typed_data';

class ThermalPrinterService {
  static final ThermalPrinterService _instance = ThermalPrinterService._();
  factory ThermalPrinterService() => _instance;
  ThermalPrinterService._();

  String? _connectedDevice;
  bool _isConnected = false;

  bool get isConnected => _isConnected;
  String? get connectedDevice => _connectedDevice;

  /// Scan for nearby Bluetooth printers
  Future<List<PrinterDevice>> scanDevices() async {
    // Production: use flutter_blue_plus or bluetooth_print package
    return [
      PrinterDevice(name: 'Sunmi V2s', address: 'AA:BB:CC:DD:EE:FF', type: PrinterType.sunmi),
      PrinterDevice(name: 'PAX A920', address: '11:22:33:44:55:66', type: PrinterType.pax),
    ];
  }

  /// Connect to a printer
  Future<bool> connect(PrinterDevice device) async {
    try {
      // Production: establish BLE/Bluetooth Classic connection
      _connectedDevice = device.name;
      _isConnected = true;
      return true;
    } catch (e) {
      _isConnected = false;
      return false;
    }
  }

  /// Disconnect from printer
  Future<void> disconnect() async {
    _connectedDevice = null;
    _isConnected = false;
  }

  /// Print a transaction receipt
  Future<bool> printReceipt(TransactionReceipt receipt) async {
    if (!_isConnected) return false;

    try {
      final commands = _buildReceiptCommands(receipt);
      // Production: send commands via BLE/Bluetooth Classic
      return true;
    } catch (e) {
      return false;
    }
  }

  /// Build ESC/POS commands for receipt
  List<int> _buildReceiptCommands(TransactionReceipt receipt) {
    final List<int> commands = [];

    // ESC/POS initialization
    commands.addAll([0x1B, 0x40]); // Initialize printer

    // Center align
    commands.addAll([0x1B, 0x61, 0x01]);

    // Bold on + double height
    commands.addAll([0x1B, 0x45, 0x01]);
    commands.addAll(_textToBytes('54Link Agent Banking'));
    commands.addAll([0x0A]); // Line feed
    commands.addAll([0x1B, 0x45, 0x00]); // Bold off

    commands.addAll(_textToBytes('================================'));
    commands.addAll([0x0A]);

    // Left align
    commands.addAll([0x1B, 0x61, 0x00]);

    // Transaction details
    commands.addAll(_textToBytes('Type: ${receipt.type}'));
    commands.addAll([0x0A]);
    commands.addAll(_textToBytes('Amount: NGN ${receipt.amount}'));
    commands.addAll([0x0A]);
    commands.addAll(_textToBytes('Ref: ${receipt.reference}'));
    commands.addAll([0x0A]);
    commands.addAll(_textToBytes('Date: ${receipt.date}'));
    commands.addAll([0x0A]);
    commands.addAll(_textToBytes('Agent: ${receipt.agentName}'));
    commands.addAll([0x0A]);

    if (receipt.customerPhone != null) {
      commands.addAll(_textToBytes('Customer: ${receipt.customerPhone}'));
      commands.addAll([0x0A]);
    }

    commands.addAll(_textToBytes('================================'));
    commands.addAll([0x0A]);

    // Center align for status
    commands.addAll([0x1B, 0x61, 0x01]);
    commands.addAll([0x1B, 0x45, 0x01]); // Bold
    commands.addAll(_textToBytes(receipt.status == 'success' ? 'SUCCESSFUL' : 'FAILED'));
    commands.addAll([0x0A]);
    commands.addAll([0x1B, 0x45, 0x00]); // Bold off

    // Footer
    commands.addAll([0x0A]);
    commands.addAll(_textToBytes('Thank you for banking with us'));
    commands.addAll([0x0A]);
    commands.addAll(_textToBytes('Powered by 54Link'));
    commands.addAll([0x0A, 0x0A, 0x0A]); // Feed

    // Cut paper
    commands.addAll([0x1D, 0x56, 0x00]);

    return commands;
  }

  List<int> _textToBytes(String text) {
    return text.codeUnits;
  }
}

// ── Models ──────────────────────────────────────────────────────────────────

class PrinterDevice {
  final String name;
  final String address;
  final PrinterType type;
  PrinterDevice({required this.name, required this.address, required this.type});
}

enum PrinterType { sunmi, pax, generic }

class TransactionReceipt {
  final String type;
  final String amount;
  final String reference;
  final String date;
  final String agentName;
  final String status;
  final String? customerPhone;
  final String? customerName;

  TransactionReceipt({
    required this.type,
    required this.amount,
    required this.reference,
    required this.date,
    required this.agentName,
    required this.status,
    this.customerPhone,
    this.customerName,
  });
}
