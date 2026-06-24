import 'package:flutter/material.dart';
import '../services/api_service.dart';

class EcommerceCheckoutScreen extends StatefulWidget {
  const EcommerceCheckoutScreen({super.key});
  @override
  State<EcommerceCheckoutScreen> createState() => _EcommerceCheckoutScreenState();
}

class _EcommerceCheckoutScreenState extends State<EcommerceCheckoutScreen> {
  int _step = 0;
  bool _loading = false;
  String _error = '';
  Map<String, dynamic> _cart = {};
  List<dynamic> _items = [];
  double _subTotal = 0;
  double _shippingFee = 500;
  double _tax = 0;
  String _currency = 'NGN';
  String _paymentMethod = 'card';
  final _addressController = TextEditingController();
  final _phoneController = TextEditingController();
  final _nameController = TextEditingController();
  String _sessionId = '';

  @override
  void initState() {
    super.initState();
    _loadCart();
  }

  Future<void> _loadCart() async {
    setState(() => _loading = true);
    try {
      final result = await ApiService.instance.get('/ecommerceCart/getCart', queryParams: {'customerId': '1'});
      setState(() {
        _cart = result ?? {};
        _items = result?['items'] ?? [];
        _subTotal = (result?['subTotal'] ?? 0).toDouble();
        _currency = result?['currency'] ?? 'NGN';
        _tax = _subTotal * 0.075;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _initiateCheckout() async {
    setState(() => _loading = true);
    try {
      final result = await ApiService.instance.post('/ecommerceOrders/createOrder', body: {
        'customerId': 1,
        'items': _items.map((i) => {
          'sku': i['sku'],
          'productId': i['productId'],
          'quantity': i['quantity'],
          'unitPrice': i['unitPrice'],
          'merchantId': i['merchantId'] ?? 1,
        }).toList(),
        'shippingAddress': _addressController.text,
        'phone': _phoneController.text,
        'paymentMethod': _paymentMethod,
        'currency': _currency,
      });
      setState(() {
        _sessionId = result?['orderId']?.toString() ?? '';
        _step = 2;
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  double get _total => _subTotal + _shippingFee + _tax;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  Text(_error, textAlign: TextAlign.center),
                  ElevatedButton(onPressed: () { setState(() { _error = ''; }); }, child: const Text('Dismiss')),
                ]))
              : Stepper(
                  currentStep: _step,
                  onStepContinue: () {
                    if (_step == 0 && _nameController.text.isNotEmpty && _addressController.text.isNotEmpty) {
                      setState(() => _step = 1);
                    } else if (_step == 1) {
                      _initiateCheckout();
                    }
                  },
                  onStepCancel: () { if (_step > 0) setState(() => _step--); },
                  steps: [
                    Step(
                      title: const Text('Shipping Details'),
                      isActive: _step >= 0,
                      content: Column(children: [
                        TextField(controller: _nameController, decoration: const InputDecoration(labelText: 'Full Name', border: OutlineInputBorder())),
                        const SizedBox(height: 12),
                        TextField(controller: _phoneController, decoration: const InputDecoration(labelText: 'Phone Number', border: OutlineInputBorder()), keyboardType: TextInputType.phone),
                        const SizedBox(height: 12),
                        TextField(controller: _addressController, decoration: const InputDecoration(labelText: 'Delivery Address', border: OutlineInputBorder()), maxLines: 2),
                      ]),
                    ),
                    Step(
                      title: const Text('Payment & Review'),
                      isActive: _step >= 1,
                      content: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        const Text('Payment Method', style: TextStyle(fontWeight: FontWeight.bold)),
                        RadioListTile(value: 'card', groupValue: _paymentMethod, onChanged: (v) => setState(() => _paymentMethod = v!), title: const Text('Card (Paystack/Flutterwave)'), dense: true),
                        RadioListTile(value: 'bank_transfer', groupValue: _paymentMethod, onChanged: (v) => setState(() => _paymentMethod = v!), title: const Text('Bank Transfer'), dense: true),
                        RadioListTile(value: 'ussd', groupValue: _paymentMethod, onChanged: (v) => setState(() => _paymentMethod = v!), title: const Text('USSD'), dense: true),
                        RadioListTile(value: 'cod', groupValue: _paymentMethod, onChanged: (v) => setState(() => _paymentMethod = v!), title: const Text('Cash on Delivery'), dense: true),
                        const Divider(),
                        _row('Subtotal', '$_currency ${_subTotal.toStringAsFixed(2)}'),
                        _row('Shipping', '$_currency ${_shippingFee.toStringAsFixed(2)}'),
                        _row('VAT (7.5%)', '$_currency ${_tax.toStringAsFixed(2)}'),
                        const Divider(),
                        _row('Total', '$_currency ${_total.toStringAsFixed(2)}', bold: true),
                      ]),
                    ),
                    Step(
                      title: const Text('Confirmation'),
                      isActive: _step >= 2,
                      content: Column(children: [
                        const Icon(Icons.check_circle, size: 64, color: Colors.green),
                        const SizedBox(height: 16),
                        const Text('Order Placed!', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                        if (_sessionId.isNotEmpty) Text('Order #$_sessionId', style: const TextStyle(color: Colors.grey)),
                        const SizedBox(height: 24),
                        ElevatedButton(
                          onPressed: () => Navigator.pushNamed(context, '/ecommerce-orders'),
                          child: const Text('View My Orders'),
                        ),
                      ]),
                    ),
                  ],
                ),
    );
  }

  Widget _row(String label, String value, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label), Text(value, style: TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal)),
      ]),
    );
  }
}
