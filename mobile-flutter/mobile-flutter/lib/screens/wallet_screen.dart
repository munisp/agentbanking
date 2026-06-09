import 'package:flutter/material.dart';
import '../services/api_service.dart';

class WalletScreen extends StatefulWidget {
  const WalletScreen({super.key});
  @override
  State<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends State<WalletScreen> {
  Map<String, dynamic>? _wallet;
  bool _loading = true;
  bool _balanceVisible = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getWallet();
      setState(() { _wallet = data; _loading = false; });
    } catch (_) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final balance = _wallet != null ? (_wallet!['balance'] ?? 0) / 100.0 : 0.0;
    return Scaffold(
      appBar: AppBar(title: const Text('My Wallet')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                color: Theme.of(context).colorScheme.primary,
                child: Column(children: [
                  Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Text(_balanceVisible
                        ? '₦${balance.toStringAsFixed(2)}'
                        : '₦ ••••••',
                        style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold,
                            color: Colors.white)),
                    IconButton(
                      icon: Icon(_balanceVisible ? Icons.visibility_off : Icons.visibility,
                          color: Colors.white),
                      onPressed: () => setState(() => _balanceVisible = !_balanceVisible),
                    ),
                  ]),
                  const Text('Available Balance', style: TextStyle(color: Colors.white70)),
                ]),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                  _QuickAction(icon: Icons.send, label: 'Send',
                      onTap: () => Navigator.pushNamed(context, '/send-money')),
                  _QuickAction(icon: Icons.download, label: 'Receive',
                      onTap: () => Navigator.pushNamed(context, '/receive-money')),
                  _QuickAction(icon: Icons.history, label: 'History',
                      onTap: () => Navigator.pushNamed(context, '/transaction-history')),
                  _QuickAction(icon: Icons.credit_card, label: 'Cards',
                      onTap: () => Navigator.pushNamed(context, '/virtual-card')),
                ]),
              ),
              const Divider(),
              ListTile(
                leading: const Icon(Icons.account_balance),
                title: const Text('Linked Bank Accounts'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.pushNamed(context, '/linked-accounts'),
              ),
              ListTile(
                leading: const Icon(Icons.savings),
                title: const Text('Savings Goals'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.pushNamed(context, '/savings-goals'),
              ),
            ]),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _QuickAction({required this.icon, required this.label, required this.onTap});
  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: Column(children: [
      CircleAvatar(radius: 28,
          backgroundColor: Theme.of(context).colorScheme.primary.withOpacity(0.1),
          child: Icon(icon, color: Theme.of(context).colorScheme.primary)),
      const SizedBox(height: 4),
      Text(label, style: const TextStyle(fontSize: 12)),
    ]),
  );
}
