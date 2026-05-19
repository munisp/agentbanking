import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../services/api_client.dart';
import '../services/api_service.dart';


class PaymentRetryScreen extends ConsumerStatefulWidget {
  final String? transactionId;
  const PaymentRetryScreen({super.key, this.transactionId});

  @override
  ConsumerState<PaymentRetryScreen> createState() => _PaymentRetryScreenState();
}

class _PaymentRetryScreenState extends ConsumerState<PaymentRetryScreen> {
  bool _isLoading = true;
  bool _isRetrying = false;
  Map<String, dynamic>? _transaction;
  String? _error;
  String _selectedGateway = 'paystack';

  static const List<Map<String, String>> _gateways = [
    {'id': 'paystack', 'name': 'Paystack'},
    {'id': 'flutterwave', 'name': 'Flutterwave'},
    {'id': 'monnify', 'name': 'Monnify'},
    {'id': 'nibss', 'name': 'NIBSS NIP'},
  ];

  @override
  void initState() {
    super.initState();
    _loadTransaction();
  }

  Future<void> _loadTransaction() async {
    setState(() { _isLoading = true; _error = null; });
    try {
      if (widget.transactionId != null) {
        final auth = ref.read(authProvider);
        final response = await ApiClient.instance.get(
          '/api/trpc/transactions.getById?input={"id":"${widget.transactionId}"}',
          token: auth.token,
        );
        setState(() => _transaction = response['result']?['data'] as Map<String, dynamic>?);
      } else {
        // Show failed transactions list
        final auth = ref.read(authProvider);
        final response = await ApiClient.instance.get(
          '/api/trpc/transactions.list?input={"limit":10,"status":"failed"}',
          token: auth.token,
        );
        final txs = response['result']?['data']?['transactions'] as List?;
        if (txs != null && txs.isNotEmpty) {
          setState(() => _transaction = txs.first as Map<String, dynamic>);
        }
      }
    } catch (e) {
      setState(() => _error = 'Failed to load transaction: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _retryPayment() async {
    if (_transaction == null) return;
    setState(() { _isRetrying = true; _error = null; });
    try {
      final auth = ref.read(authProvider);
      await ApiClient.instance.post(
        '/api/trpc/transactions.retry',
        body: {
          'id': _transaction!['id'],
          'gateway': _selectedGateway,
        },
        token: auth.token,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Payment retry initiated successfully'),
            backgroundColor: Colors.green,
          ),
        );
        context.go('/history');
      }
    } catch (e) {
      setState(() => _error = 'Retry failed: $e');
    } finally {
      if (mounted) setState(() => _isRetrying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Retry Payment', style: TextStyle(color: Colors.white)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => context.go('/history'),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1A56DB)))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Failed transaction card
                  if (_transaction != null) ...[
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xFF1E293B),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.red.withOpacity(0.3)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.red.withOpacity(0.2),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Text('FAILED', style: TextStyle(color: Colors.red, fontSize: 11, fontWeight: FontWeight.bold)),
                              ),
                              const Spacer(),
                              Text(
                                _transaction!['reference'] as String? ?? 'N/A',
                                style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            '₦${_transaction!['amount']?.toString() ?? '0'}',
                            style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            _transaction!['type'] as String? ?? 'Transaction',
                            style: const TextStyle(color: Color(0xFF94A3B8)),
                          ),
                          if (_transaction!['errorMessage'] != null) ...[
                            const SizedBox(height: 8),
                            Text(
                              'Error: ${_transaction!['errorMessage']}',
                              style: const TextStyle(color: Colors.red, fontSize: 12),
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],
                  const Text('Select Gateway for Retry', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  ..._gateways.map((g) => RadioListTile<String>(
                    value: g['id']!,
                    groupValue: _selectedGateway,
                    onChanged: (v) => setState(() => _selectedGateway = v!),
                    title: Text(g['name']!, style: const TextStyle(color: Colors.white)),
                    activeColor: const Color(0xFF1A56DB),
                    tileColor: const Color(0xFF1E293B),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12),
                  )).toList(),
                  const SizedBox(height: 24),
                  if (_error != null) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(_error!, style: const TextStyle(color: Colors.red)),
                    ),
                    const SizedBox(height: 16),
                  ],
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: (_transaction != null && !_isRetrying) ? _retryPayment : null,
                      icon: _isRetrying
                          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.replay),
                      label: Text(_isRetrying ? 'Retrying...' : 'Retry Payment'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1A56DB),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: () => context.go('/history'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFF94A3B8),
                        side: const BorderSide(color: Color(0xFF475569)),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text('Cancel'),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
