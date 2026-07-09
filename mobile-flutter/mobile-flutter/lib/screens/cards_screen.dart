import 'package:flutter/material.dart';
import '../services/api_service.dart';

class CardsScreen extends StatefulWidget {
  const CardsScreen({super.key});
  @override
  State<CardsScreen> createState() => _CardsScreenState();
}

class _CardsScreenState extends State<CardsScreen> {
  final _api = ApiService();
  List<dynamic> _cards = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadCards();
  }

  Future<void> _loadCards() async {
    try {
      final cards = await _api.getVirtualCards();
      setState(() { _cards = cards; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _createCard() async {
    try {
      await _api.createVirtualCard(label: 'My Card', currency: 'NGN');
      await _loadCards();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Virtual card created')),
      );
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Cards'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: _createCard,
            tooltip: 'Create Virtual Card',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error'))
              : _cards.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.credit_card_off, size: 64, color: Colors.grey),
                          const SizedBox(height: 16),
                          const Text('No virtual cards yet', style: TextStyle(fontSize: 18)),
                          const SizedBox(height: 8),
                          ElevatedButton.icon(
                            onPressed: _createCard,
                            icon: const Icon(Icons.add),
                            label: const Text('Create Virtual Card'),
                          ),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _loadCards,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _cards.length,
                        itemBuilder: (context, i) {
                          final card = _cards[i];
                          return Card(
                            margin: const EdgeInsets.only(bottom: 12),
                            child: ListTile(
                              leading: const Icon(Icons.credit_card, color: Colors.blue),
                              title: Text(card['label'] ?? 'Virtual Card'),
                              subtitle: Text('${card['currency'] ?? 'NGN'} • ${card['status'] ?? 'active'}'),
                              trailing: Text(
                                '₦${(card['balance'] ?? 0).toStringAsFixed(2)}',
                                style: const TextStyle(fontWeight: FontWeight.bold),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
