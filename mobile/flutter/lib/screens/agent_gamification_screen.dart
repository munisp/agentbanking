import 'package:flutter/material.dart';

class AgentGamificationScreen extends StatefulWidget {
  const AgentGamificationScreen({super.key});

  @override
  State<AgentGamificationScreen> createState() => _AgentGamificationScreenState();
}

class _AgentGamificationScreenState extends State<AgentGamificationScreen> {
  bool _isLoading = true;
  String _searchQuery = '';
  final List<String> _features = [
        'Leaderboards',\n                'Achievement badges',\n                'Team challenges',\n                'Commission multipliers',
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
        title: Text('Gamification'),
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
                          hintText: 'Search gamification...',
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
                                  Icon(Icons.emoji_events, size: 28),
                                  const SizedBox(width: 12),
                                  Text(
                                    'Gamification',
                                    style: theme.textTheme.headlineSmall,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              ..._features
                                  .where((f) => f.toLowerCase().contains(_searchQuery.toLowerCase()))
                                  .map((feature) => ListTile(
                                        leading: Icon(Icons.emoji_events, size: 20),
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
