import 'package:flutter/material.dart';
import '../services/api_service.dart';

class EcommerceProductCatalogScreen extends StatefulWidget {
  const EcommerceProductCatalogScreen({super.key});
  @override
  State<EcommerceProductCatalogScreen> createState() => _EcommerceProductCatalogScreenState();
}

class _EcommerceProductCatalogScreenState extends State<EcommerceProductCatalogScreen> {
  List<dynamic> _products = [];
  List<dynamic> _categories = [];
  bool _loading = true;
  String _error = '';
  String _search = '';
  int? _selectedCategory;
  String _sortBy = 'newest';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final results = await Future.wait([
        ApiService.instance.get('/ecommerceCatalog/listProducts', queryParams: {'limit': '50'}),
        ApiService.instance.get('/ecommerceCatalog/listCategories'),
      ]);
      setState(() {
        _products = results[0]?['products'] ?? [];
        _categories = results[1]?['categories'] ?? [];
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _searchProducts(String query) async {
    if (query.length < 2) return;
    setState(() => _loading = true);
    try {
      final result = await ApiService.instance.get('/ecommerceCatalog/searchProducts', queryParams: {'query': query, 'limit': '30'});
      setState(() { _products = result?['products'] ?? []; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _addToCart(dynamic product) async {
    try {
      await ApiService.instance.post('/ecommerceCart/addItem', body: {
        'customerId': 1,
        'sku': product['sku'],
        'productId': product['id'],
        'name': product['name'],
        'quantity': 1,
        'unitPrice': product['price'],
        'merchantId': product['merchantId'] ?? 1,
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${product['name']} added to cart')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  List<dynamic> get _filtered {
    var list = _products;
    if (_selectedCategory != null) {
      list = list.where((p) => p['categoryId'] == _selectedCategory).toList();
    }
    if (_search.isNotEmpty) {
      final q = _search.toLowerCase();
      list = list.where((p) => (p['name'] ?? '').toString().toLowerCase().contains(q)).toList();
    }
    return list;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Product Catalog'),
        actions: [
          IconButton(icon: const Icon(Icons.shopping_cart), onPressed: () => Navigator.pushNamed(context, '/ecommerce-cart')),
          IconButton(icon: const Icon(Icons.refresh), onPressed: () { setState(() => _loading = true); _loadData(); }),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  Text(_error, textAlign: TextAlign.center),
                  ElevatedButton(onPressed: () { setState(() { _error = ''; _loading = true; }); _loadData(); }, child: const Text('Retry')),
                ]))
              : Column(children: [
                  // Search + Filter bar
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(children: [
                      Expanded(child: TextField(
                        decoration: InputDecoration(
                          hintText: 'Search products...', prefixIcon: const Icon(Icons.search),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                          isDense: true,
                        ),
                        onChanged: (v) { setState(() => _search = v); if (v.length >= 2) _searchProducts(v); },
                      )),
                      const SizedBox(width: 8),
                      PopupMenuButton<String>(
                        icon: const Icon(Icons.sort),
                        onSelected: (v) => setState(() => _sortBy = v),
                        itemBuilder: (_) => [
                          const PopupMenuItem(value: 'newest', child: Text('Newest')),
                          const PopupMenuItem(value: 'price_low', child: Text('Price: Low to High')),
                          const PopupMenuItem(value: 'price_high', child: Text('Price: High to Low')),
                          const PopupMenuItem(value: 'name', child: Text('Name A-Z')),
                        ],
                      ),
                    ]),
                  ),
                  // Categories horizontal scroll
                  if (_categories.isNotEmpty) SizedBox(
                    height: 40,
                    child: ListView.builder(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _categories.length + 1,
                      itemBuilder: (ctx, i) {
                        if (i == 0) return Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ChoiceChip(label: const Text('All'), selected: _selectedCategory == null, onSelected: (_) => setState(() => _selectedCategory = null)),
                        );
                        final cat = _categories[i - 1];
                        return Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ChoiceChip(label: Text(cat['name'] ?? ''), selected: _selectedCategory == cat['id'], onSelected: (_) => setState(() => _selectedCategory = cat['id'])),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 8),
                  // Product grid
                  Expanded(
                    child: _filtered.isEmpty
                        ? const Center(child: Text('No products found'))
                        : GridView.builder(
                            padding: const EdgeInsets.all(8),
                            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2, childAspectRatio: 0.7,
                              crossAxisSpacing: 8, mainAxisSpacing: 8,
                            ),
                            itemCount: _filtered.length,
                            itemBuilder: (ctx, i) {
                              final product = _filtered[i];
                              final price = product['price'] ?? '0';
                              return Card(
                                elevation: 2,
                                child: InkWell(
                                  onTap: () {},
                                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    Expanded(
                                      flex: 3,
                                      child: Container(
                                        width: double.infinity,
                                        decoration: BoxDecoration(color: Colors.grey[200], borderRadius: const BorderRadius.vertical(top: Radius.circular(4))),
                                        child: product['imageUrl'] != null
                                            ? Image.network(product['imageUrl'], fit: BoxFit.cover, errorBuilder: (_, __, ___) => const Icon(Icons.image, size: 48))
                                            : const Icon(Icons.inventory_2, size: 48, color: Colors.grey),
                                      ),
                                    ),
                                    Expanded(flex: 2, child: Padding(
                                      padding: const EdgeInsets.all(8),
                                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                        Text(product['name'] ?? '', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                                        const SizedBox(height: 4),
                                        Text('NGN $price', style: TextStyle(color: Theme.of(context).primaryColor, fontWeight: FontWeight.bold)),
                                        const Spacer(),
                                        SizedBox(width: double.infinity, child: ElevatedButton.icon(
                                          onPressed: () => _addToCart(product),
                                          icon: const Icon(Icons.add_shopping_cart, size: 16),
                                          label: const Text('Add', style: TextStyle(fontSize: 12)),
                                          style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 4)),
                                        )),
                                      ]),
                                    )),
                                  ]),
                                ),
                              );
                            },
                          ),
                  ),
                ]),
    );
  }
}
