import 'package:flutter/material.dart';
import 'dart:async';

/// SIM Orchestrator Screen — Multi-network provider management for POS terminals.
///
/// Features (parity with PWA SimOrchestratorTab):
///   1. Per-slot signal strength with carrier color coding
///   2. Active SIM slot indicator with score badge
///   3. Carrier ranking table with SLA data
///   4. Failover history timeline
///   5. Transaction-type-aware recommendations
///   6. USSD quick-dial for balance checks
///   7. Failover policy configuration
class SimOrchestratorScreen extends StatefulWidget {
  const SimOrchestratorScreen({super.key});

  @override
  State<SimOrchestratorScreen> createState() => _SimOrchestratorScreenState();
}

class _SimOrchestratorScreenState extends State<SimOrchestratorScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  String _terminalId = 'TERM-001';
  int _activeSlot = 0;
  List<SimSlot> _slots = [];
  List<CarrierRank> _rankings = [];
  List<FailoverEvent> _failoverHistory = [];
  bool _autoFailover = true;
  int _minSignalDbm = -90;
  int _maxLatencyMs = 500;
  String _selectedTxType = 'general';
  String? _recommendation;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadData();
  }

  void _loadData() {
    setState(() {
      _slots = [
        SimSlot(index: 0, carrier: 'MTN', name: 'MTN Nigeria', signalDbm: -65,
            networkType: '4G', isPreferred: true, score: 82, iccid: '89234...001'),
        SimSlot(index: 1, carrier: 'AIRTEL', name: 'Airtel Nigeria', signalDbm: -75,
            networkType: '4G', isPreferred: false, score: 71, iccid: '89234...002'),
        SimSlot(index: 2, carrier: 'GLO', name: 'Globacom', signalDbm: -88,
            networkType: '3G', isPreferred: false, score: 48, iccid: '89234...003'),
      ];
      _activeSlot = 0;
      _rankings = [
        CarrierRank(carrier: 'MTN', reliability: 92.0, latency: 45, cost: 0.35, sla: 99.5, rank: 1, financialPref: true),
        CarrierRank(carrier: 'AIRTEL', reliability: 88.0, latency: 55, cost: 0.30, sla: 99.0, rank: 2, financialPref: true),
        CarrierRank(carrier: 'GLO', reliability: 82.0, latency: 65, cost: 0.25, sla: 98.0, rank: 3, financialPref: false),
        CarrierRank(carrier: '9MOBILE', reliability: 78.0, latency: 70, cost: 0.28, sla: 97.5, rank: 4, financialPref: false),
      ];
      _failoverHistory = [
        FailoverEvent(from: 'GLO', to: 'MTN', reason: 'signal -95dBm < -90dBm', time: DateTime.now().subtract(const Duration(hours: 2))),
        FailoverEvent(from: 'AIRTEL', to: 'MTN', reason: 'latency 650ms > 500ms', time: DateTime.now().subtract(const Duration(hours: 8))),
      ];
    });
  }

  Color _carrierColor(String carrier) {
    switch (carrier) {
      case 'MTN': return const Color(0xFFD4A843);
      case 'AIRTEL': return const Color(0xFFE05555);
      case 'GLO': return const Color(0xFF4CAF50);
      case '9MOBILE': return const Color(0xFF4A90D9);
      default: return Colors.grey;
    }
  }

  Color _signalColor(int dbm) {
    if (dbm >= -65) return Colors.green;
    if (dbm >= -75) return Colors.blue;
    if (dbm >= -85) return Colors.amber;
    return Colors.red;
  }

  String _signalLabel(int dbm) {
    if (dbm >= -65) return 'Excellent';
    if (dbm >= -75) return 'Good';
    if (dbm >= -85) return 'Fair';
    return 'Poor';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0E1A),
        title: const Text('SIM Orchestrator', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.grey,
          indicatorColor: const Color(0xFF4A90D9),
          tabs: const [
            Tab(text: 'Slots', icon: Icon(Icons.sim_card, size: 18)),
            Tab(text: 'Rankings', icon: Icon(Icons.leaderboard, size: 18)),
            Tab(text: 'History', icon: Icon(Icons.history, size: 18)),
            Tab(text: 'Policy', icon: Icon(Icons.settings, size: 18)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSlotsTab(),
          _buildRankingsTab(),
          _buildHistoryTab(),
          _buildPolicyTab(),
        ],
      ),
    );
  }

  Widget _buildSlotsTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Terminal selector
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFF141B2D),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFF1E2A3E)),
          ),
          child: Row(children: [
            const Icon(Icons.terminal, color: Colors.grey, size: 20),
            const SizedBox(width: 8),
            Text(_terminalId, style: const TextStyle(color: Colors.white, fontFamily: 'monospace')),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.2),
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Text('Online', style: TextStyle(color: Colors.green, fontSize: 12)),
            ),
          ]),
        ),
        const SizedBox(height: 16),

        // SIM slot cards
        ..._slots.map((slot) => _buildSlotCard(slot)),

        const SizedBox(height: 16),

        // Recommendation card
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF141B2D),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFF1E2A3E)),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Recommendation', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            DropdownButton<String>(
              value: _selectedTxType,
              dropdownColor: const Color(0xFF141B2D),
              style: const TextStyle(color: Colors.white),
              items: ['general', 'financial', 'payment', 'transfer', 'settlement', 'telemetry']
                  .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                  .toList(),
              onChanged: (v) {
                setState(() {
                  _selectedTxType = v ?? 'general';
                  final isFinancial = ['financial', 'payment', 'transfer', 'settlement'].contains(_selectedTxType);
                  _recommendation = isFinancial
                      ? 'MTN recommended: 92% reliability, 99.5% SLA'
                      : 'GLO recommended: best cost/performance (₦0.25/MB)';
                });
              },
            ),
            if (_recommendation != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(_recommendation!, style: TextStyle(color: Colors.blue.shade300, fontSize: 13)),
              ),
          ]),
        ),
      ],
    );
  }

  Widget _buildSlotCard(SimSlot slot) {
    final isActive = slot.index == _activeSlot;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF141B2D),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isActive ? const Color(0xFF4A90D9) : const Color(0xFF1E2A3E),
          width: isActive ? 2 : 1,
        ),
      ),
      child: Row(children: [
        // Slot badge
        Container(
          width: 48, height: 48,
          decoration: BoxDecoration(
            color: _carrierColor(slot.carrier).withOpacity(0.2),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: _carrierColor(slot.carrier).withOpacity(0.5)),
          ),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text('SIM${slot.index + 1}', style: TextStyle(color: _carrierColor(slot.carrier), fontSize: 10, fontWeight: FontWeight.bold)),
            if (isActive) const Icon(Icons.check_circle, color: Colors.green, size: 14),
          ]),
        ),
        const SizedBox(width: 12),
        // Info
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(slot.name, style: TextStyle(color: _carrierColor(slot.carrier), fontWeight: FontWeight.bold)),
          Text('${slot.networkType} · ${slot.signalDbm} dBm · ${_signalLabel(slot.signalDbm)}',
              style: TextStyle(color: _signalColor(slot.signalDbm), fontSize: 12)),
        ])),
        // Score
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: slot.score > 70 ? Colors.green.withOpacity(0.2) : Colors.amber.withOpacity(0.2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text('${slot.score}', style: TextStyle(
            color: slot.score > 70 ? Colors.green : Colors.amber,
            fontWeight: FontWeight.bold,
          )),
        ),
      ]),
    );
  }

  Widget _buildRankingsTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Carrier Rankings (Nigeria)', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        ..._rankings.map((r) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: const Color(0xFF141B2D),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: const Color(0xFF1E2A3E)),
          ),
          child: Row(children: [
            Container(
              width: 28, height: 28,
              decoration: BoxDecoration(color: _carrierColor(r.carrier).withOpacity(0.3), shape: BoxShape.circle),
              child: Center(child: Text('#${r.rank}', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold))),
            ),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(r.carrier, style: TextStyle(color: _carrierColor(r.carrier), fontWeight: FontWeight.bold)),
              Text('${r.reliability}% reliable · ${r.latency}ms · ₦${r.cost}/MB',
                  style: const TextStyle(color: Colors.grey, fontSize: 11)),
            ])),
            if (r.financialPref)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(color: Colors.green.withOpacity(0.2), borderRadius: BorderRadius.circular(4)),
                child: const Text('Financial ✓', style: TextStyle(color: Colors.green, fontSize: 10)),
              ),
          ]),
        )),
      ],
    );
  }

  Widget _buildHistoryTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Failover History', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        if (_failoverHistory.isEmpty)
          const Center(child: Text('No failover events', style: TextStyle(color: Colors.grey)))
        else
          ..._failoverHistory.map((e) => Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF141B2D),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF1E2A3E)),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Text(e.from, style: TextStyle(color: _carrierColor(e.from), fontWeight: FontWeight.bold)),
                const Icon(Icons.arrow_forward, color: Colors.grey, size: 16),
                Text(e.to, style: TextStyle(color: _carrierColor(e.to), fontWeight: FontWeight.bold)),
                const Spacer(),
                Text(_formatTime(e.time), style: const TextStyle(color: Colors.grey, fontSize: 11)),
              ]),
              const SizedBox(height: 4),
              Text(e.reason, style: const TextStyle(color: Colors.orange, fontSize: 12)),
            ]),
          )),
      ],
    );
  }

  Widget _buildPolicyTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Failover Policy', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        _buildPolicyToggle('Auto Failover', _autoFailover, (v) => setState(() => _autoFailover = v)),
        const SizedBox(height: 16),
        _buildPolicySlider('Min Signal (dBm)', _minSignalDbm.toDouble(), -120, -50,
            (v) => setState(() => _minSignalDbm = v.round())),
        _buildPolicySlider('Max Latency (ms)', _maxLatencyMs.toDouble(), 100, 2000,
            (v) => setState(() => _maxLatencyMs = v.round())),
        const SizedBox(height: 24),
        const Text('USSD Quick Dial', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ...[
          ('MTN', '*556#', '*131*4#'),
          ('AIRTEL', '*123#', '*140#'),
          ('GLO', '*124#', '*127*0#'),
          ('9MOBILE', '*232#', '*229*0#'),
        ].map((c) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFF141B2D),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFF1E2A3E)),
          ),
          child: Row(children: [
            Text(c.$1, style: TextStyle(color: _carrierColor(c.$1), fontWeight: FontWeight.bold, fontSize: 14)),
            const Spacer(),
            Text('Balance: ${c.$2}', style: const TextStyle(color: Colors.grey, fontFamily: 'monospace', fontSize: 12)),
            const SizedBox(width: 12),
            Text('Data: ${c.$3}', style: const TextStyle(color: Colors.grey, fontFamily: 'monospace', fontSize: 12)),
          ]),
        )),
      ],
    );
  }

  Widget _buildPolicyToggle(String label, bool value, ValueChanged<bool> onChanged) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF141B2D),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF1E2A3E)),
      ),
      child: Row(children: [
        Text(label, style: const TextStyle(color: Colors.white)),
        const Spacer(),
        Switch(value: value, onChanged: onChanged, activeColor: Colors.green),
      ]),
    );
  }

  Widget _buildPolicySlider(String label, double value, double min, double max, ValueChanged<double> onChanged) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF141B2D),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF1E2A3E)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(label, style: const TextStyle(color: Colors.white)),
          const Spacer(),
          Text('${value.round()}', style: const TextStyle(color: Colors.blue, fontFamily: 'monospace')),
        ]),
        Slider(value: value, min: min, max: max, onChanged: onChanged, activeColor: Colors.blue),
      ]),
    );
  }

  String _formatTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }
}

class SimSlot {
  final int index;
  final String carrier;
  final String name;
  final int signalDbm;
  final String networkType;
  final bool isPreferred;
  final int score;
  final String iccid;

  SimSlot({required this.index, required this.carrier, required this.name,
      required this.signalDbm, required this.networkType, required this.isPreferred,
      required this.score, required this.iccid});
}

class CarrierRank {
  final String carrier;
  final double reliability;
  final int latency;
  final double cost;
  final double sla;
  final int rank;
  final bool financialPref;

  CarrierRank({required this.carrier, required this.reliability, required this.latency,
      required this.cost, required this.sla, required this.rank, required this.financialPref});
}

class FailoverEvent {
  final String from;
  final String to;
  final String reason;
  final DateTime time;

  FailoverEvent({required this.from, required this.to, required this.reason, required this.time});
}
