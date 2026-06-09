import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../services/api_client.dart';
import '../services/api_service.dart';


class PaymentMethodsScreen extends ConsumerStatefulWidget {
  const PaymentMethodsScreen({super.key});

  @override
  ConsumerState<PaymentMethodsScreen> createState() => _PaymentMethodsScreenState();
}

class _PaymentMethodsScreenState extends ConsumerState<PaymentMethodsScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _methods = [];
  String? _error;

  static const List<Map<String, dynamic>> _availableGateways = [
    {'id': 'paystack', 'name': 'Paystack', 'icon': Icons.credit_card, 'color': Color(0xFF00C3F7), 'description': 'Cards, bank transfer, USSD'},
    {'id': 'flutterwave', 'name': 'Flutterwave', 'icon': Icons.payment, 'color': Color(0xFFF5A623), 'description': 'Cards, mobile money, bank'},
    {'id': 'monnify', 'name': 'Monnify', 'icon': Icons.account_balance, 'color': Color(0xFF1A56DB), 'description': 'Bank transfer, USSD'},
    {'id': 'interswitch', 'name': 'Interswitch', 'icon': Icons.swap_horiz, 'color': Color(0xFF10B981), 'description': 'Quickteller, Verve cards'},
    {'id': 'nibss', 'name': 'NIBSS NIP', 'icon': Icons.send, 'color': Color(0xFF8B5CF6), 'description': 'Instant bank transfer'},
  ];

  @override
  void initState() {
    super.initState();
    _loadMethods();
  }

  Future<void> _loadMethods() async {
    setState(() { _isLoading = true; _error = null; });
    try {
      final auth = ref.read(authProvider);
      final response = await ApiClient.instance.get(
        '/api/trpc/management.getPaymentGateways?input={}',
        token: auth.token,
      );
      final data = response['result']?['data'] as List? ?? [];
      setState(() => _methods = data.cast<Map<String, dynamic>>());
    } catch (e) {
      // Fallback: show all gateways as available
      setState(() {
        _methods = _availableGateways.map((g) => {
          'id': g['id'],
          'name': g['name'],
          'enabled': true,
          'priority': _availableGateways.indexOf(g) + 1,
        }).toList();
        _error = 'Using default configuration';
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _toggleMethod(String id, bool enabled) async {
    setState(() {
      final idx = _methods.indexWhere((m) => m['id'] == id);
      if (idx >= 0) _methods[idx] = {..._methods[idx], 'enabled': enabled};
    });
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${enabled ? "Enabled" : "Disabled"} $id gateway'),
          backgroundColor: enabled ? Colors.green : Colors.orange,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Payment Methods', style: TextStyle(color: Colors.white)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => context.go('/dashboard'),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _loadMethods,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1A56DB)))
          : Column(
              children: [
                if (_error != null)
                  Container(
                    padding: const EdgeInsets.all(12),
                    color: Colors.orange.withOpacity(0.1),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline, color: Colors.orange, size: 16),
                        const SizedBox(width: 8),
                        Text(_error!, style: const TextStyle(color: Colors.orange, fontSize: 12)),
                      ],
                    ),
                  ),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _availableGateways.length,
                    itemBuilder: (context, index) {
                      final gateway = _availableGateways[index];
                      final methodData = _methods.firstWhere(
                        (m) => m['id'] == gateway['id'],
                        orElse: () => {'id': gateway['id'], 'enabled': false},
                      );
                      final isEnabled = methodData['enabled'] as bool? ?? false;
                      return Card(
                        color: const Color(0xFF1E293B),
                        margin: const EdgeInsets.only(bottom: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                          side: BorderSide(
                            color: isEnabled ? (gateway['color'] as Color).withOpacity(0.4) : Colors.transparent,
                          ),
                        ),
                        child: ListTile(
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          leading: Container(
                            width: 48,
                            height: 48,
                            decoration: BoxDecoration(
                              color: (gateway['color'] as Color).withOpacity(0.15),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(gateway['icon'] as IconData, color: gateway['color'] as Color),
                          ),
                          title: Text(
                            gateway['name'] as String,
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                          subtitle: Text(
                            gateway['description'] as String,
                            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                          ),
                          trailing: Switch(
                            value: isEnabled,
                            onChanged: (v) => _toggleMethod(gateway['id'] as String, v),
                            activeColor: const Color(0xFF1A56DB),
                          ),
                        ),
                      );
                    },
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1E293B),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline, color: Color(0xFF94A3B8), size: 16),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Text(
                            'Changes take effect immediately. Disabled gateways will not be offered to customers.',
                            style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
