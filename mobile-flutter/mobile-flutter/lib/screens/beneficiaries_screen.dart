import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../services/api_client.dart';
import '../services/api_service.dart';


class BeneficiariesScreen extends ConsumerStatefulWidget {
  const BeneficiariesScreen({super.key});

  @override
  ConsumerState<BeneficiariesScreen> createState() => _BeneficiariesScreenState();
}

class _BeneficiariesScreenState extends ConsumerState<BeneficiariesScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _beneficiaries = [];
  List<Map<String, dynamic>> _filtered = [];
  String? _error;
  final _searchCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadBeneficiaries();
    _searchCtrl.addListener(_onSearch);
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  void _onSearch() {
    final q = _searchCtrl.text.toLowerCase();
    setState(() {
      _filtered = q.isEmpty
          ? _beneficiaries
          : _beneficiaries.where((b) =>
              (b['name'] as String? ?? '').toLowerCase().contains(q) ||
              (b['accountNumber'] as String? ?? '').contains(q) ||
              (b['bank'] as String? ?? '').toLowerCase().contains(q)).toList();
    });
  }

  Future<void> _loadBeneficiaries() async {
    setState(() { _isLoading = true; _error = null; });
    try {
      final auth = ref.read(authProvider);
      final response = await ApiClient.instance.get(
        '/api/trpc/customer.listBeneficiaries?input={"limit":100}',
        token: auth.token,
      );
      final items = (response['result']?['data']?['beneficiaries'] as List?) ?? [];
      setState(() {
        _beneficiaries = items.cast<Map<String, dynamic>>();
        _filtered = _beneficiaries;
      });
    } catch (e) {
      setState(() => _error = 'Failed to load beneficiaries: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _deleteBeneficiary(String id, String name) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Remove Beneficiary', style: TextStyle(color: Colors.white)),
        content: Text('Remove $name from your beneficiaries?', style: const TextStyle(color: Color(0xFF94A3B8))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      setState(() {
        _beneficiaries.removeWhere((b) => b['id'] == id);
        _filtered.removeWhere((b) => b['id'] == id);
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$name removed'), backgroundColor: Colors.orange),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Beneficiaries', style: TextStyle(color: Colors.white)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => context.go('/dashboard'),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_add, color: Colors.white),
            onPressed: () => context.go('/add-beneficiary'),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchCtrl,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Search by name, account, or bank...',
                hintStyle: const TextStyle(color: Color(0xFF475569)),
                prefixIcon: const Icon(Icons.search, color: Color(0xFF94A3B8)),
                filled: true,
                fillColor: const Color(0xFF1E293B),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF1A56DB)))
                : _error != null && _beneficiaries.isEmpty
                    ? Center(child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.error_outline, color: Colors.red, size: 48),
                          const SizedBox(height: 12),
                          Text(_error!, style: const TextStyle(color: Colors.red)),
                          const SizedBox(height: 16),
                          ElevatedButton(onPressed: _loadBeneficiaries, child: const Text('Retry')),
                        ],
                      ))
                    : _filtered.isEmpty
                        ? _buildEmptyState()
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemCount: _filtered.length,
                            itemBuilder: (context, index) {
                              final b = _filtered[index];
                              final initials = (b['name'] as String? ?? 'U')
                                  .split(' ')
                                  .take(2)
                                  .map((w) => w.isNotEmpty ? w[0] : '')
                                  .join()
                                  .toUpperCase();
                              return Card(
                                color: const Color(0xFF1E293B),
                                margin: const EdgeInsets.only(bottom: 8),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                child: ListTile(
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                                  leading: CircleAvatar(
                                    backgroundColor: const Color(0xFF1A56DB),
                                    child: Text(initials, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                  ),
                                  title: Text(
                                    b['name'] as String? ?? 'Unknown',
                                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                                  ),
                                  subtitle: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(b['accountNumber'] as String? ?? '', style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13)),
                                      Text(b['bank'] as String? ?? '', style: const TextStyle(color: Color(0xFF64748B), fontSize: 12)),
                                    ],
                                  ),
                                  trailing: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                        icon: const Icon(Icons.send, color: Color(0xFF1A56DB), size: 20),
                                        onPressed: () => context.go('/send-money'),
                                        tooltip: 'Send money',
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.delete_outline, color: Colors.red, size: 20),
                                        onPressed: () => _deleteBeneficiary(b['id'] as String? ?? '', b['name'] as String? ?? ''),
                                        tooltip: 'Remove',
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.go('/add-beneficiary'),
        backgroundColor: const Color(0xFF1A56DB),
        icon: const Icon(Icons.person_add),
        label: const Text('Add Beneficiary'),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.people_outline, size: 64, color: Color(0xFF475569)),
          const SizedBox(height: 16),
          Text(
            _searchCtrl.text.isNotEmpty ? 'No results found' : 'No Beneficiaries',
            style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            _searchCtrl.text.isNotEmpty
                ? 'Try a different search term'
                : 'Add beneficiaries to send money quickly',
            style: const TextStyle(color: Color(0xFF94A3B8)),
          ),
          if (_searchCtrl.text.isEmpty) ...[
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => context.go('/add-beneficiary'),
              icon: const Icon(Icons.person_add),
              label: const Text('Add First Beneficiary'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1A56DB),
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
