import 'package:flutter/material.dart';
import '../services/api_service.dart';

class EcommerceMerchantStorefrontScreen extends StatefulWidget {
  const EcommerceMerchantStorefrontScreen({super.key});
  @override
  State<EcommerceMerchantStorefrontScreen> createState() => _EcommerceMerchantStorefrontScreenState();
}

class _EcommerceMerchantStorefrontScreenState extends State<EcommerceMerchantStorefrontScreen> {
  Map<String, dynamic>? _store;
  List<dynamic> _products = [];
  bool _loading = true;
  String _error = '';
  String _search = '';

  @override
  void initState() {
    super.initState();
    _loadStore();
  }

  Future<void> _loadStore() async {
    try {
      final storeResult = await ApiService.instance.get('/agentStore/getMyStore', queryParams: {'agentId': '1'});
      final productsResult = await ApiService.instance.get('/ecommerceCatalog/listProducts', queryParams: {'limit': '50'});
      setState(() {
        _store = storeResult;
        _products = productsResult?['products'] ?? [];
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  List<dynamic> get _filtered {
    if (_search.isEmpty) return _products;
    final q = _search.toLowerCase();
    return _products.where((p) => (p['name'] ?? '').toString().toLowerCase().contains(q)).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  Text(_error, textAlign: TextAlign.center),
                  ElevatedButton(onPressed: () { setState(() { _error = ''; _loading = true; }); _loadStore(); }, child: const Text('Retry')),
                ]))
              : CustomScrollView(slivers: [
                  SliverAppBar(
                    expandedHeight: 200,
                    floating: false, pinned: true,
                    flexibleSpace: FlexibleSpaceBar(
                      title: Text(_store?['storeName'] ?? 'Store'),
                      background: Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topLeft, end: Alignment.bottomRight,
                            colors: [Theme.of(context).primaryColor, Theme.of(context).primaryColor.withOpacity(0.7)],
                          ),
                        ),
                        child: _store?['bannerUrl'] != null
                            ? Image.network(_store!['bannerUrl'], fit: BoxFit.cover, errorBuilder: (_, __, ___) => const SizedBox())
                            : const Center(child: Icon(Icons.store, size: 64, color: Colors.white38)),
                      ),
                    ),
                    actions: [
                      IconButton(icon: const Icon(Icons.share), onPressed: () {}),
                      IconButton(icon: const Icon(Icons.shopping_cart), onPressed: () => Navigator.pushNamed(context, '/ecommerce-cart')),
                    ],
                  ),
                  // Store info
                  SliverToBoxAdapter(child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      if (_store?['description'] != null) Text(_store!['description'], style: const TextStyle(color: Colors.grey)),
                      const SizedBox(height: 8),
                      Row(children: [
                        if (_store?['averageRating'] != null) ...[
                          const Icon(Icons.star, size: 16, color: Colors.amber),
                          Text(' ${_store!['averageRating']}', style: const TextStyle(fontWeight: FontWeight.bold)),
                          const SizedBox(width: 16),
                        ],
                        if (_store?['city'] != null) ...[
                          const Icon(Icons.location_on, size: 16, color: Colors.grey),
                          Text(' ${_store!['city']}, ${_store?['state'] ?? ''}'),
                        ],
                      ]),
                      if (_store?['deliveryEnabled'] == true) Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Chip(avatar: const Icon(Icons.delivery_dining, size: 16), label: const Text('Delivery Available')),
                      ),
                    ]),
                  )),
                  // Search bar
                  SliverToBoxAdapter(child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: TextField(
                      decoration: InputDecoration(
                        hintText: 'Search products...', prefixIcon: const Icon(Icons.search),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)), isDense: true,
                      ),
                      onChanged: (v) => setState(() => _search = v),
                    ),
                  )),
                  const SliverToBoxAdapter(child: SizedBox(height: 12)),
                  // Products grid
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    sliver: _filtered.isEmpty
                        ? const SliverToBoxAdapter(child: Center(child: Padding(padding: EdgeInsets.all(32), child: Text('No products available'))))
                        : SliverGrid(
                            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2, childAspectRatio: 0.75, crossAxisSpacing: 8, mainAxisSpacing: 8,
                            ),
                            delegate: SliverChildBuilderDelegate(
                              (ctx, i) {
                                final product = _filtered[i];
                                return Card(
                                  child: InkWell(
                                    onTap: () {},
                                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                      Expanded(
                                        child: Container(
                                          width: double.infinity,
                                          decoration: BoxDecoration(color: Colors.grey[200], borderRadius: const BorderRadius.vertical(top: Radius.circular(4))),
                                          child: product['imageUrl'] != null
                                              ? Image.network(product['imageUrl'], fit: BoxFit.cover, errorBuilder: (_, __, ___) => const Icon(Icons.image, size: 40))
                                              : const Icon(Icons.inventory_2, size: 40, color: Colors.grey),
                                        ),
                                      ),
                                      Padding(
                                        padding: const EdgeInsets.all(8),
                                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                          Text(product['name'] ?? '', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                                          const SizedBox(height: 4),
                                          Text('NGN ${product['price']}', style: TextStyle(color: Theme.of(context).primaryColor, fontWeight: FontWeight.bold, fontSize: 15)),
                                        ]),
                                      ),
                                    ]),
                                  ),
                                );
                              },
                              childCount: _filtered.length,
                            ),
                          ),
                  ),
                ]),
    );
  }
}
