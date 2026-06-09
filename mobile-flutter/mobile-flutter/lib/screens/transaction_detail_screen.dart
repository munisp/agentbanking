import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../services/api_client.dart';
import '../services/api_service.dart';


class TransactionDetailScreen extends ConsumerStatefulWidget {
  final String transactionId;
  const TransactionDetailScreen({super.key, required this.transactionId});

  @override
  ConsumerState<TransactionDetailScreen> createState() => _TransactionDetailScreenState();
}

class _TransactionDetailScreenState extends ConsumerState<TransactionDetailScreen> {
  bool _isLoading = true;
  Map<String, dynamic>? _transaction;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadTransaction();
  }

  Future<void> _loadTransaction() async {
    setState(() { _isLoading = true; _error = null; });
    try {
      final auth = ref.read(authProvider);
      final response = await ApiClient.instance.get(
        '/api/trpc/transactions.getById?input={"id":"${widget.transactionId}"}',
        token: auth.token,
      );
      setState(() => _transaction = response['result']?['data'] as Map<String, dynamic>?);
    } catch (e) {
      setState(() => _error = 'Failed to load transaction: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Color _statusColor(String? status) {
    switch (status?.toLowerCase()) {
      case 'completed': case 'success': return const Color(0xFF10B981);
      case 'pending': return Colors.orange;
      case 'failed': case 'error': return Colors.red;
      default: return const Color(0xFF94A3B8);
    }
  }

  IconData _typeIcon(String? type) {
    switch (type?.toLowerCase()) {
      case 'cash_in': case 'deposit': return Icons.arrow_downward;
      case 'cash_out': case 'withdrawal': return Icons.arrow_upward;
      case 'transfer': return Icons.swap_horiz;
      case 'airtime': return Icons.phone_android;
      case 'bill': case 'utility': return Icons.receipt_long;
      default: return Icons.payment;
    }
  }

  void _copyToClipboard(String text, String label) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label copied'), duration: const Duration(seconds: 2)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Transaction Details', style: TextStyle(color: Colors.white)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => context.go('/history'),
        ),
        actions: [
          if (_transaction != null)
            IconButton(
              icon: const Icon(Icons.share, color: Colors.white),
              onPressed: () => _copyToClipboard(
                _transaction!['reference'] as String? ?? '',
                'Reference',
              ),
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1A56DB)))
          : _error != null
              ? Center(child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline, color: Colors.red, size: 48),
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                    const SizedBox(height: 16),
                    ElevatedButton(onPressed: _loadTransaction, child: const Text('Retry')),
                  ],
                ))
              : _transaction == null
                  ? const Center(child: Text('Transaction not found', style: TextStyle(color: Color(0xFF94A3B8))))
                  : _buildDetails(),
    );
  }

  Widget _buildDetails() {
    final tx = _transaction!;
    final status = tx['status'] as String?;
    final type = tx['type'] as String?;
    final amount = tx['amount'];
    final statusColor = _statusColor(status);

    return SingleChildScrollView(
      child: Column(
        children: [
          // Hero section
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(32),
            color: const Color(0xFF1E293B),
            child: Column(
              children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(36),
                  ),
                  child: Icon(_typeIcon(type), color: statusColor, size: 36),
                ),
                const SizedBox(height: 16),
                Text(
                  '₦${amount?.toString() ?? '0'}',
                  style: const TextStyle(color: Colors.white, fontSize: 36, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    (status ?? 'UNKNOWN').toUpperCase(),
                    style: TextStyle(color: statusColor, fontWeight: FontWeight.bold, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
          // Details list
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                _buildDetailCard([
                  _detailRow('Type', _formatType(type), copyable: false),
                  _detailRow('Reference', tx['reference'] as String? ?? 'N/A', copyable: true),
                  _detailRow('Date', _formatDate(tx['createdAt']), copyable: false),
                  if (tx['completedAt'] != null)
                    _detailRow('Completed', _formatDate(tx['completedAt']), copyable: false),
                ]),
                const SizedBox(height: 12),
                if (tx['customer'] != null || tx['recipientName'] != null)
                  _buildDetailCard([
                    if (tx['customer'] != null)
                      _detailRow('Customer', tx['customer'] as String? ?? '', copyable: false),
                    if (tx['recipientName'] != null)
                      _detailRow('Recipient', tx['recipientName'] as String? ?? '', copyable: false),
                    if (tx['recipientAccount'] != null)
                      _detailRow('Account', tx['recipientAccount'] as String? ?? '', copyable: true),
                    if (tx['recipientBank'] != null)
                      _detailRow('Bank', tx['recipientBank'] as String? ?? '', copyable: false),
                  ]),
                const SizedBox(height: 12),
                _buildDetailCard([
                  _detailRow('Terminal', tx['terminalId'] as String? ?? 'N/A', copyable: false),
                  _detailRow('Agent', tx['agentCode'] as String? ?? 'N/A', copyable: false),
                  if (tx['fee'] != null)
                    _detailRow('Fee', '₦${tx['fee']}', copyable: false),
                  if (tx['channel'] != null)
                    _detailRow('Channel', tx['channel'] as String? ?? '', copyable: false),
                ]),
                if (tx['errorMessage'] != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.red.withOpacity(0.3)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Error Details', style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 4),
                        Text(tx['errorMessage'] as String, style: const TextStyle(color: Colors.red, fontSize: 13)),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                if (status == 'failed')
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () => context.go('/payment-retry/${widget.transactionId}'),
                      icon: const Icon(Icons.replay),
                      label: const Text('Retry Payment'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1A56DB),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                  ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => context.go('/receipt/${widget.transactionId}'),
                    icon: const Icon(Icons.receipt),
                    label: const Text('View Receipt'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF94A3B8),
                      side: const BorderSide(color: Color(0xFF475569)),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailCard(List<Widget> rows) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: rows.asMap().entries.map((e) {
          final isLast = e.key == rows.length - 1;
          return Column(
            children: [
              e.value,
              if (!isLast) const Divider(color: Color(0xFF334155), height: 1),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _detailRow(String label, String value, {required bool copyable}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 14)),
          const Spacer(),
          Flexible(
            child: Text(
              value,
              style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500),
              textAlign: TextAlign.right,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (copyable) ...[
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () => _copyToClipboard(value, label),
              child: const Icon(Icons.copy, size: 16, color: Color(0xFF94A3B8)),
            ),
          ],
        ],
      ),
    );
  }

  String _formatType(String? type) {
    if (type == null) return 'Unknown';
    return type.replaceAll('_', ' ').split(' ').map((w) => w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : '').join(' ');
  }

  String _formatDate(dynamic dateVal) {
    if (dateVal == null) return 'N/A';
    try {
      final dt = DateTime.parse(dateVal.toString()).toLocal();
      return '${dt.day}/${dt.month}/${dt.year} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return dateVal.toString();
    }
  }
}
