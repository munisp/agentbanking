import 'package:flutter/material.dart';

class CrossBorderRemittanceScreen extends StatefulWidget {
  const CrossBorderRemittanceScreen({super.key});

  @override
  State<CrossBorderRemittanceScreen> createState() => _CrossBorderRemittanceScreenState();
}

class _CrossBorderRemittanceScreenState extends State<CrossBorderRemittanceScreen> {
  bool _isLoading = true;
  String _searchQuery = '';
  final List<String> _features = [
        'ECOWAS corridors',\n                'FX rate quotes',\n                'Send remittance',\n                'Transfer history',
  ];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    // Simulate API call
    await Future.delayed(const Duration(milliseconds: 800));
    if (mounted) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: Text('Cross-Border'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() => _isLoading = true);
              _loadData();
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadData,
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: TextField(
                        decoration: InputDecoration(
                          hintText: 'Search cross-border...',
                          prefixIcon: const Icon(Icons.search),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          filled: true,
                          fillColor: isDark
                              ? Colors.grey[800]
                              : Colors.grey[100],
                        ),
                        onChanged: (v) => setState(() => _searchQuery = v),
                      ),
                    ),
                  ),
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(Icons.language, size: 28),
                                  const SizedBox(width: 12),
                                  Text(
                                    'Cross-Border',
                                    style: theme.textTheme.headlineSmall,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              ..._features
                                  .where((f) => f.toLowerCase().contains(_searchQuery.toLowerCase()))
                                  .map((feature) => ListTile(
                                        leading: Icon(Icons.language, size: 20),
                                        title: Text(feature),
                                        trailing: const Icon(Icons.chevron_right),
                                        onTap: () {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text('Opening: $feature')),
                                          );
                                        },
                                      )),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
