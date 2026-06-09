import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../services/api_client.dart';
import '../services/api_service.dart';


class RecurringPaymentsScreen extends ConsumerStatefulWidget {
  const RecurringPaymentsScreen({super.key});

  @override
  ConsumerState<RecurringPaymentsScreen> createState() => _RecurringPaymentsScreenState();
}

class _RecurringPaymentsScreenState extends ConsumerState<RecurringPaymentsScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _schedules = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSchedules();
  }

  Future<void> _loadSchedules() async {
    setState(() { _isLoading = true; _error = null; });
    try {
      final auth = ref.read(authProvider);
      final response = await ApiClient.instance.get(
        '/api/trpc/transactions.list?input={"limit":50,"type":"recurring"}',
        token: auth.token,
      );
      final items = (response['result']?['data']?['transactions'] as List?) ?? [];
      setState(() => _schedules = items.cast<Map<String, dynamic>>());
    } catch (e) {
      setState(() => _error = 'Failed to load recurring payments: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _cancelSchedule(String id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Cancel Schedule', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Are you sure you want to cancel this recurring payment?',
          style: TextStyle(color: Color(0xFF94A3B8)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep', style: TextStyle(color: Color(0xFF94A3B8))),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Cancel Payment'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      setState(() => _schedules.removeWhere((s) => s['id'] == id));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recurring payment cancelled'), backgroundColor: Colors.orange),
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
        title: const Text('Recurring Payments', style: TextStyle(color: Colors.white)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => context.go('/dashboard'),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _loadSchedules,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showCreateScheduleDialog(),
        backgroundColor: const Color(0xFF1A56DB),
        icon: const Icon(Icons.add),
        label: const Text('New Schedule'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1A56DB)))
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.red)))
              : _schedules.isEmpty
                  ? _buildEmptyState()
                  : _buildScheduleList(),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.repeat, size: 64, color: Color(0xFF475569)),
          const SizedBox(height: 16),
          const Text(
            'No Recurring Payments',
            style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          const Text(
            'Set up automatic bill payments and transfers',
            style: TextStyle(color: Color(0xFF94A3B8)),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _showCreateScheduleDialog,
            icon: const Icon(Icons.add),
            label: const Text('Create Schedule'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1A56DB),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildScheduleList() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _schedules.length,
      itemBuilder: (context, index) {
        final schedule = _schedules[index];
        return Card(
          color: const Color(0xFF1E293B),
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          child: ListTile(
            contentPadding: const EdgeInsets.all(16),
            leading: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: const Color(0xFF1A56DB).withOpacity(0.2),
                borderRadius: BorderRadius.circular(24),
              ),
              child: const Icon(Icons.repeat, color: Color(0xFF1A56DB)),
            ),
            title: Text(
              schedule['type'] ?? 'Recurring Payment',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text(
                  schedule['customer'] ?? 'Unknown recipient',
                  style: const TextStyle(color: Color(0xFF94A3B8)),
                ),
                const SizedBox(height: 2),
                Text(
                  '₦${schedule['amount']?.toString() ?? '0'} • Monthly',
                  style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.w600),
                ),
              ],
            ),
            trailing: IconButton(
              icon: const Icon(Icons.cancel_outlined, color: Colors.red),
              onPressed: () => _cancelSchedule(schedule['id'] ?? ''),
            ),
          ),
        );
      },
    );
  }

  void _showCreateScheduleDialog() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1E293B),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Padding(
        padding: EdgeInsets.only(
          left: 24, right: 24, top: 24,
          bottom: MediaQuery.of(context).viewInsets.bottom + 24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('New Recurring Payment', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            const Text('Feature coming soon — recurring payment scheduling will be available in the next release.', style: TextStyle(color: Color(0xFF94A3B8))),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1A56DB), foregroundColor: Colors.white),
                child: const Text('Close'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
