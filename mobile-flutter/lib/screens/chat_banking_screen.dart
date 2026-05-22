import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';

class ChatBankingScreen extends ConsumerStatefulWidget {
  const ChatBankingScreen({super.key});

  @override
  ConsumerState<ChatBankingScreen> createState() => _ChatBankingScreenState();
}

class _ChatBankingScreenState extends ConsumerState<ChatBankingScreen> {
  Map<String, dynamic>? _stats;
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _loading = true);
    try {
      final api = ApiService();
      final statsResp = await api.get('/api/trpc/chat_banking.getStats');
      final listResp = await api.get('/api/trpc/chat_banking.list?input={"limit":20,"offset":0}');
      setState(() {
        _stats = statsResp.data?['result']?['data'] ?? {};
        _items = List<Map<String, dynamic>>.from(
          listResp.data?['result']?['data']?['items'] ?? [],
        );
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat Banking'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline, size: 48, color: theme.colorScheme.error),
                      const SizedBox(height: 16),
                      Text(_error, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      ElevatedButton(onPressed: _loadData, child: const Text('Retry')),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: CustomScrollView(
                    slivers: [
                      // Header
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Chat Banking',
                                style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'WhatsApp and conversational banking',
                                style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                      ),
                      // Stats Grid
                      SliverPadding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        sliver: SliverGrid(
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            mainAxisSpacing: 12,
                            crossAxisSpacing: 12,
                            childAspectRatio: 1.8,
                          ),
                          delegate: SliverChildBuilderDelegate(
                            (context, index) {
                              final entries = (_stats ?? {}).entries.toList();
                              if (index >= entries.length) return null;
                              final entry = entries[index];
                              return Card(
                                child: Padding(
                                  padding: const EdgeInsets.all(12),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Text(
                                        entry.key.replaceAllMapped(
                                          RegExp(r'([A-Z])'),
                                          (m) => ' ${m.group(0)}',
                                        ).trim(),
                                        style: theme.textTheme.labelSmall?.copyWith(color: Colors.grey),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '${entry.value}',
                                        style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            },
                            childCount: (_stats ?? {}).length,
                          ),
                        ),
                      ),
                      // Items List
                      SliverPadding(
                        padding: const EdgeInsets.all(16),
                        sliver: SliverToBoxAdapter(
                          child: Text(
                            'Records (${_items.length})',
                            style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                      SliverList(
                        delegate: SliverChildBuilderDelegate(
                          (context, index) {
                            final item = _items[index];
                            return Card(
                              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                              child: ListTile(
                                leading: CircleAvatar(
                                  child: Text('${item['id'] ?? index + 1}'),
                                ),
                                title: Text(item['name'] ?? item['partnerName'] ?? item['customerName'] ?? 'Record ${index + 1}'),
                                subtitle: Text(item['status'] ?? 'active'),
                                trailing: Chip(
                                  label: Text(
                                    item['status'] ?? 'active',
                                    style: const TextStyle(fontSize: 11),
                                  ),
                                  backgroundColor: _getStatusColor(item['status']),
                                ),
                                onTap: () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text('Viewing record ${item['id']}')),
                                  );
                                },
                              ),
                            );
                          },
                          childCount: _items.length,
                        ),
                      ),
                      // Empty state
                      if (_items.isEmpty)
                        SliverToBoxAdapter(
                          child: Padding(
                            padding: const EdgeInsets.all(32),
                            child: Column(
                              children: [
                                Icon(Icons.inbox, size: 64, color: Colors.grey[400]),
                                const SizedBox(height: 16),
                                Text('No records yet', style: theme.textTheme.bodyLarge),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
    );
  }

  Color _getStatusColor(String? status) {
    switch (status?.toLowerCase()) {
      case 'active':
      case 'healthy':
      case 'verified':
      case 'approved':
      case 'confirmed':
      case 'paid':
      case 'online':
      case 'connected':
        return Colors.green[100]!;
      case 'pending':
      case 'review':
      case 'dormant':
      case 'idle':
      case 'partial':
      case 'maintenance':
      case 'failover':
      case 'syncing':
        return Colors.orange[100]!;
      case 'suspended':
      case 'failed':
      case 'declined':
      case 'rejected':
      case 'overdue':
      case 'defaulted':
      case 'offline':
      case 'tampered':
      case 'escalated':
      case 'lost':
        return Colors.red[100]!;
      default:
        return Colors.grey[200]!;
    }
  }
}
