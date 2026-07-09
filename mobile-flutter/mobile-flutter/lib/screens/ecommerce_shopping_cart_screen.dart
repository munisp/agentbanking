import 'package:flutter/material.dart';
import '../services/api_service.dart';

class EcommerceShoppingCartScreen extends StatefulWidget {
  const EcommerceShoppingCartScreen({super.key});
  @override
  State<EcommerceShoppingCartScreen> createState() => _EcommerceShoppingCartScreenState();
}

class _EcommerceShoppingCartScreenState extends State<EcommerceShoppingCartScreen> {
  List<dynamic> _items = [];
  bool _loading = true;
  String _error = '';
  double _subTotal = 0;
  double _discount = 0;
  String _couponCode = '';
  String _currency = 'NGN';

  @override
  void initState() {
    super.initState();
    _loadCart();
  }

  Future<void> _loadCart() async {
    try {
      final result = await ApiService.instance.get('/ecommerceCart/getCart', queryParams: {'customerId': '1'});
      setState(() {
        _items = result?['items'] ?? [];
        _subTotal = (result?['subTotal'] ?? 0).toDouble();
        _discount = (result?['discountAmount'] ?? 0).toDouble();
        _couponCode = result?['couponCode'] ?? '';
        _currency = result?['currency'] ?? 'NGN';
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _updateQuantity(String sku, int quantity) async {
    try {
      await ApiService.instance.post('/ecommerceCart/updateItem', body: {
        'customerId': 1, 'sku': sku, 'quantity': quantity,
      });
      _loadCart();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  Future<void> _removeItem(String sku) async {
    try {
      await ApiService.instance.post('/ecommerceCart/removeItem', body: {
        'customerId': 1, 'sku': sku,
      });
      _loadCart();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  Future<void> _applyCoupon(String code) async {
    try {
      await ApiService.instance.post('/ecommerceCart/applyCoupon', body: {
        'customerId': 1, 'couponCode': code,
      });
      _loadCart();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Coupon applied!')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Invalid coupon: $e')));
    }
  }

  Future<void> _clearCart() async {
    try {
      await ApiService.instance.post('/ecommerceCart/clearCart', body: {'customerId': 1});
      _loadCart();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final total = _subTotal - _discount;
    return Scaffold(
      appBar: AppBar(
        title: Text('Cart (${_items.length} items)'),
        actions: [
          if (_items.isNotEmpty) IconButton(icon: const Icon(Icons.delete_sweep), onPressed: _clearCart, tooltip: 'Clear Cart'),
          IconButton(icon: const Icon(Icons.refresh), onPressed: () { setState(() => _loading = true); _loadCart(); }),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  Text(_error, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  ElevatedButton(onPressed: () { setState(() { _error = ''; _loading = true; }); _loadCart(); }, child: const Text('Retry')),
                ]))
              : _items.isEmpty
                  ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                      const Icon(Icons.shopping_cart_outlined, size: 64, color: Colors.grey),
                      const SizedBox(height: 16),
                      const Text('Your cart is empty', style: TextStyle(fontSize: 18, color: Colors.grey)),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: () => Navigator.pushNamed(context, '/ecommerce-catalog'),
                        child: const Text('Browse Products'),
                      ),
                    ]))
                  : Column(children: [
                      Expanded(
                        child: ListView.builder(
                          padding: const EdgeInsets.all(8),
                          itemCount: _items.length,
                          itemBuilder: (ctx, i) {
                            final item = _items[i];
                            final qty = item['quantity'] ?? 1;
                            final price = double.tryParse(item['unitPrice']?.toString() ?? '0') ?? 0;
                            return Card(
                              margin: const EdgeInsets.symmetric(vertical: 4),
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Row(children: [
                                  // Product image placeholder
                                  Container(
                                    width: 60, height: 60,
                                    decoration: BoxDecoration(color: Colors.grey[200], borderRadius: BorderRadius.circular(8)),
                                    child: item['imageUrl'] != null
                                        ? ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.network(item['imageUrl'], fit: BoxFit.cover, errorBuilder: (_, __, ___) => const Icon(Icons.image)))
                                        : const Icon(Icons.image, color: Colors.grey),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    Text(item['name'] ?? 'Unknown', style: const TextStyle(fontWeight: FontWeight.bold)),
                                    Text('SKU: ${item['sku']}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                                    Text('$_currency ${price.toStringAsFixed(2)}', style: TextStyle(color: Theme.of(context).primaryColor, fontWeight: FontWeight.w600)),
                                  ])),
                                  // Quantity controls
                                  Column(children: [
                                    Row(mainAxisSize: MainAxisSize.min, children: [
                                      IconButton(
                                        icon: const Icon(Icons.remove_circle_outline, size: 20),
                                        onPressed: qty > 1 ? () => _updateQuantity(item['sku'], qty - 1) : null,
                                      ),
                                      Text('$qty', style: const TextStyle(fontWeight: FontWeight.bold)),
                                      IconButton(
                                        icon: const Icon(Icons.add_circle_outline, size: 20),
                                        onPressed: () => _updateQuantity(item['sku'], qty + 1),
                                      ),
                                    ]),
                                    Text('$_currency ${(price * qty).toStringAsFixed(2)}', style: const TextStyle(fontSize: 12)),
                                  ]),
                                  IconButton(
                                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                                    onPressed: () => _removeItem(item['sku']),
                                  ),
                                ]),
                              ),
                            );
                          },
                        ),
                      ),
                      // Coupon section
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Row(children: [
                          Expanded(child: TextField(
                            decoration: InputDecoration(
                              hintText: _couponCode.isEmpty ? 'Enter coupon code' : _couponCode,
                              isDense: true, border: const OutlineInputBorder(),
                            ),
                            onSubmitted: _applyCoupon,
                          )),
                          const SizedBox(width: 8),
                          ElevatedButton(onPressed: () => _applyCoupon(_couponCode), child: const Text('Apply')),
                        ]),
                      ),
                      // Order summary
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.grey[50],
                          border: Border(top: BorderSide(color: Colors.grey[300]!)),
                        ),
                        child: Column(children: [
                          _summaryRow('Subtotal', '$_currency ${_subTotal.toStringAsFixed(2)}'),
                          if (_discount > 0) _summaryRow('Discount', '-$_currency ${_discount.toStringAsFixed(2)}', color: Colors.green),
                          const Divider(),
                          _summaryRow('Total', '$_currency ${total.toStringAsFixed(2)}', bold: true),
                          const SizedBox(height: 12),
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              onPressed: () => Navigator.pushNamed(context, '/ecommerce-checkout'),
                              style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                              child: Text('Proceed to Checkout ($_currency ${total.toStringAsFixed(2)})'),
                            ),
                          ),
                        ]),
                      ),
                    ]),
    );
  }

  Widget _summaryRow(String label, String value, {bool bold = false, Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label),
        Text(value, style: TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal, color: color)),
      ]),
    );
  }
}
