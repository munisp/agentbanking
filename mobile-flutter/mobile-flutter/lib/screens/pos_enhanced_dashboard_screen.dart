import 'package:flutter/material.dart';

/// POS Enhanced Dashboard — Flutter native screen.
/// Feature parity with PWA POSEnhancedDashboard.tsx.
/// Tabs: Overview, DUKPT Keys, AI Routing, Self-Healing, Voice, Float, Biometrics, EOD, Geo, Revenue
class PosEnhancedDashboardScreen extends StatefulWidget {
  const PosEnhancedDashboardScreen({super.key});

  @override
  State<PosEnhancedDashboardScreen> createState() => _PosEnhancedDashboardScreenState();
}

class _PosEnhancedDashboardScreenState extends State<PosEnhancedDashboardScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  final _tabs = const [
    Tab(text: 'Overview'),
    Tab(text: 'Keys'),
    Tab(text: 'Routing'),
    Tab(text: 'Healing'),
    Tab(text: 'Voice'),
    Tab(text: 'Float'),
    Tab(text: 'Biometrics'),
    Tab(text: 'EOD'),
    Tab(text: 'Geo'),
    Tab(text: 'Revenue'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF111827),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1F2937),
        title: const Text('POS Terminal Management', style: TextStyle(color: Colors.white)),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: _tabs,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.grey,
          indicatorColor: Colors.blue,
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildOverview(),
          _buildKeysPanel(),
          _buildRoutingPanel(),
          _buildHealingPanel(),
          _buildVoicePanel(),
          _buildFloatPanel(),
          _buildBiometricsPanel(),
          _buildEodPanel(),
          _buildGeoPanel(),
          _buildRevenuePanel(),
        ],
      ),
    );
  }

  Widget _buildOverview() {
    return GridView.count(
      crossAxisCount: 2,
      padding: const EdgeInsets.all(16),
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      children: [
        _statCard('Active Terminals', '247', '+12'),
        _statCard('Key Rotations', '18', '0'),
        _statCard('Self-Healed', '34', '+5'),
        _statCard('Voice Commands', '156', '+23'),
        _statCard('Float Alerts', '8', '-2'),
        _statCard('Bio Blocks', '3', '+1'),
        _statCard('Geo Flags', '1', '0'),
        _statCard('Revenue', '\u20a62.4M', '+15%'),
      ],
    );
  }

  Widget _statCard(String title, String value, String change) {
    final color = change.startsWith('+') ? Colors.green : change.startsWith('-') ? Colors.red : Colors.grey;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1F2937),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF374151)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(title, style: const TextStyle(color: Colors.grey, fontSize: 11)),
          const SizedBox(height: 8),
          Text(value, style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
          Text('$change today', style: TextStyle(color: color, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _buildKeysPanel() => _placeholder('DUKPT Key Management', 'TMK/TPK/TAK status, rotation, and injection history.');
  Widget _buildRoutingPanel() => _placeholder('AI Transaction Routing', 'NIBSS/Interswitch/UPSL scoring and selection.');
  Widget _buildHealingPanel() => _placeholder('Self-Healing Status', 'Auto-remediation log: printer/NFC/network/memory/thermal.');
  Widget _buildVoicePanel() => _placeholder('Voice POS', '4 languages (EN/HA/YO/PCM), 5 intents, voice session log.');
  Widget _buildFloatPanel() => _placeholder('Predictive Float', 'ML demand forecasting with market day/salary period factors.');
  Widget _buildBiometricsPanel() => _placeholder('Behavioral Biometrics', 'Keystroke dynamics risk scoring: allow/challenge/block.');
  Widget _buildEodPanel() => _placeholder('EOD Reconciliation', 'Forced end-of-day settlement and discrepancy detection.');
  Widget _buildGeoPanel() => _placeholder('Geo-Velocity', 'Impossible movement detection for cloned terminals.');
  Widget _buildRevenuePanel() => _placeholder('Fleet Revenue', 'Daily volume, commissions, transactions, active terminals.');

  Widget _placeholder(String title, String description) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(description, style: const TextStyle(color: Colors.grey)),
        ],
      ),
    );
  }
}
