import 'package:flutter/material.dart';
import '../services/api_service.dart';

class OfflinePosModeScreen extends StatefulWidget {
  const OfflinePosModeScreen({super.key});
  @override
  State<OfflinePosModeScreen> createState() => _OfflinePosModeScreenState();
}

class _OfflinePosModeScreenState extends State<OfflinePosModeScreen> {
  bool _loading = true;
  String _error = '';
  bool _sessionActive = false;
  Map<String, dynamic>? _config;
  List<Map<String, dynamic>> _pendingTransactions = [];
  double _floatSnapshot = 0;
  double _dailyUsed = 0;
  double _dailyLimit = 500000;
  String _tier = 'bronze';

  final _tierMultipliers = {
    'bronze': 1.0,
    'silver': 1.5,
    'gold': 2.0,
    'platinum': 3.0,
  };

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    setState(() => _loading = true);
    try {
      final result = await ApiService.instance.get('/api/trpc/offlinePosMode.getOfflineConfig');
      final data = result?['result']?['data']?['json'];
      setState(() {
        _config = data ?? {};
        _tier = data?['tier'] ?? 'bronze';
        _dailyLimit = (data?['maxOfflineAmount'] ?? 500000).toDouble();
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _startSession() async {
    try {
      await ApiService.instance.post(
        '/api/trpc/offlinePosMode.startSession',
        body: {'json': {'tier': _tier}},
      );
      setState(() {
        _sessionActive = true;
        _floatSnapshot = (_config?['floatBalance'] ?? 0).toDouble();
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to start session: $e')),
      );
    }
  }

  Future<void> _endSession() async {
    try {
      await ApiService.instance.post(
        '/api/trpc/offlinePosMode.endSession',
        body: {'json': {'sync': _pendingTransactions.isNotEmpty}},
      );
      setState(() {
        _sessionActive = false;
        _pendingTransactions.clear();
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to end session: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final multiplier = _tierMultipliers[_tier] ?? 1.0;
    final maxAmount = 500000 * multiplier;
    final maxQueue = (50 * multiplier).toInt();
    final remaining = maxAmount - _dailyUsed;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Offline POS Mode'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadConfig),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.red),
                  Text(_error, textAlign: TextAlign.center),
                  ElevatedButton(onPressed: _loadConfig, child: const Text('Retry')),
                ]))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Session status
                      Card(
                        color: _sessionActive ? Colors.green[50] : Colors.grey[100],
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            children: [
                              Icon(
                                _sessionActive ? Icons.wifi_off : Icons.wifi,
                                size: 40,
                                color: _sessionActive ? Colors.green : Colors.grey,
                              ),
                              const SizedBox(height: 8),
                              Text(
                                _sessionActive ? 'OFFLINE SESSION ACTIVE' : 'ONLINE',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 18,
                                  color: _sessionActive ? Colors.green[800] : Colors.grey[700],
                                ),
                              ),
                              if (_sessionActive) ...[
                                const SizedBox(height: 4),
                                Text('Float: ₦${_floatSnapshot.toStringAsFixed(0)}'),
                                Text('Pending: ${_pendingTransactions.length}/$maxQueue'),
                              ],
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Tier and limits
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Offline Limits',
                                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                              const Divider(),
                              _limitRow('Agent Tier', _tier.toUpperCase()),
                              _limitRow('Tier Multiplier', '${multiplier}x'),
                              _limitRow('Max Offline Amount', '₦${maxAmount.toStringAsFixed(0)}'),
                              _limitRow('Max Queue Size', '$maxQueue transactions'),
                              _limitRow('Max Session', '480 minutes (8 hours)'),
                              _limitRow('Risk Multiplier', '1.5x (offline fee)'),
                              const Divider(),
                              _limitRow('Daily Used', '₦${_dailyUsed.toStringAsFixed(0)}'),
                              _limitRow('Daily Remaining', '₦${remaining.toStringAsFixed(0)}'),
                              const SizedBox(height: 8),
                              LinearProgressIndicator(
                                value: (maxAmount > 0) ? (_dailyUsed / maxAmount).clamp(0, 1) : 0,
                                backgroundColor: Colors.grey[200],
                                color: remaining < maxAmount * 0.2 ? Colors.red : Colors.green,
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Session controls
                      if (!_sessionActive)
                        ElevatedButton.icon(
                          onPressed: _startSession,
                          icon: const Icon(Icons.play_arrow),
                          label: const Text('Start Offline Session'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                        )
                      else
                        ElevatedButton.icon(
                          onPressed: _endSession,
                          icon: const Icon(Icons.stop),
                          label: Text(
                            _pendingTransactions.isNotEmpty
                                ? 'End Session & Sync (${_pendingTransactions.length} pending)'
                                : 'End Session',
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.red,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                        ),
                      const SizedBox(height: 16),

                      // Pending transactions
                      if (_pendingTransactions.isNotEmpty) ...[
                        Text('Pending Transactions (${_pendingTransactions.length})',
                            style: const TextStyle(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        ..._pendingTransactions.map((txn) => Card(
                              child: ListTile(
                                leading: const Icon(Icons.pending_actions),
                                title: Text(txn['type'] ?? 'Transaction'),
                                subtitle: Text('₦${txn['amount'] ?? 0}'),
                                trailing: const Chip(label: Text('PENDING')),
                              ),
                            )),
                      ],
                    ],
                  ),
                ),
    );
  }

  Widget _limitRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.grey[700])),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
