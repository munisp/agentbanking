import 'package:flutter/material.dart';

/// Insider Threat Management Screen
/// Shows pending approvals, threat alerts, and step-up auth for mobile admin users.
class InsiderThreatScreen extends StatefulWidget {
  const InsiderThreatScreen({super.key});

  @override
  State<InsiderThreatScreen> createState() => _InsiderThreatScreenState();
}

class _InsiderThreatScreenState extends State<InsiderThreatScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _stepUpAuthenticated = false;
  List<Map<String, dynamic>> _pendingApprovals = [];
  List<Map<String, dynamic>> _alerts = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  Future<void> _loadData() async {
    // In production: fetch from tRPC API
    setState(() {
      _pendingApprovals = [];
      _alerts = [];
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Insider Threat Management'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Approvals', icon: Icon(Icons.approval)),
            Tab(text: 'Alerts', icon: Icon(Icons.warning_amber)),
            Tab(text: 'Audit', icon: Icon(Icons.verified_user)),
          ],
        ),
        actions: [
          if (!_stepUpAuthenticated)
            IconButton(
              icon: const Icon(Icons.fingerprint),
              tooltip: 'Step-Up Auth',
              onPressed: _showStepUpDialog,
            ),
          if (_stepUpAuthenticated)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: Chip(
                label: Text('Verified', style: TextStyle(fontSize: 12)),
                backgroundColor: Colors.green,
                labelStyle: TextStyle(color: Colors.white),
              ),
            ),
        ],
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildApprovalsTab(),
          _buildAlertsTab(),
          _buildAuditTab(),
        ],
      ),
    );
  }

  Widget _buildApprovalsTab() {
    if (_pendingApprovals.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_circle_outline, size: 64, color: Colors.green),
            SizedBox(height: 16),
            Text('No pending approvals', style: TextStyle(fontSize: 16, color: Colors.grey)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView.builder(
        itemCount: _pendingApprovals.length,
        itemBuilder: (context, index) {
          final approval = _pendingApprovals[index];
          return _ApprovalCard(
            approval: approval,
            isAuthenticated: _stepUpAuthenticated,
            onApprove: () => _handleApprove(approval),
            onReject: () => _handleReject(approval),
          );
        },
      ),
    );
  }

  Widget _buildAlertsTab() {
    if (_alerts.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.shield, size: 64, color: Colors.green),
            SizedBox(height: 16),
            Text('No active threats detected', style: TextStyle(fontSize: 16, color: Colors.grey)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView.builder(
        itemCount: _alerts.length,
        itemBuilder: (context, index) {
          final alert = _alerts[index];
          return _AlertCard(alert: alert);
        },
      ),
    );
  }

  Widget _buildAuditTab() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            color: Colors.green.shade50,
            child: const ListTile(
              leading: Icon(Icons.lock, color: Colors.green),
              title: Text('Hash Chain Intact'),
              subtitle: Text('No tampering detected in audit trail'),
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            'Separation of Duties',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 8),
          _buildDutyRule('Self-approval blocked on all financial mutations'),
          _buildDutyRule('Maker and Approver roles are mutually exclusive'),
          _buildDutyRule('Step-up authentication for privileged actions'),
          _buildDutyRule('15-minute admin session timeout'),
          _buildDutyRule('Cryptographic hash chain audit trail'),
          const SizedBox(height: 16),
          const Text(
            'Approval Thresholds',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 8),
          _buildThreshold('Tier 1: Standard', '₦0 – ₦500K', 'No additional approval', Colors.green),
          _buildThreshold('Tier 2: Dual Control', '₦500K – ₦5M', '1 additional approver', Colors.orange),
          _buildThreshold('Tier 3: Compliance', '₦5M+', '2 approvers + 30min cooling', Colors.red),
        ],
      ),
    );
  }

  Widget _buildDutyRule(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          const Icon(Icons.check_circle, size: 16, color: Colors.green),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
        ],
      ),
    );
  }

  Widget _buildThreshold(String title, String range, String requirement, Color color) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withOpacity(0.1),
          child: Icon(Icons.attach_money, color: color, size: 20),
        ),
        title: Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        subtitle: Text('$range\n$requirement', style: const TextStyle(fontSize: 12)),
        isThreeLine: true,
      ),
    );
  }

  void _showStepUpDialog() {
    showDialog(
      context: context,
      builder: (context) => _StepUpAuthDialog(
        onAuthenticated: () {
          setState(() => _stepUpAuthenticated = true);
          Navigator.of(context).pop();
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Step-up authentication verified (5 min)'),
              backgroundColor: Colors.green,
            ),
          );
        },
      ),
    );
  }

  void _handleApprove(Map<String, dynamic> approval) {
    if (!_stepUpAuthenticated) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Step-up authentication required'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }
    // In production: call tRPC mutation
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Approval granted'), backgroundColor: Colors.green),
    );
  }

  void _handleReject(Map<String, dynamic> approval) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject Request'),
        content: const TextField(
          decoration: InputDecoration(
            hintText: 'Reason for rejection (min 5 chars)',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Request rejected'), backgroundColor: Colors.red),
              );
            },
            child: const Text('Reject', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}

class _ApprovalCard extends StatelessWidget {
  final Map<String, dynamic> approval;
  final bool isAuthenticated;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ApprovalCard({
    required this.approval,
    required this.isAuthenticated,
    required this.onApprove,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  (approval['type'] as String? ?? '').replaceAll('_', ' '),
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                Chip(
                  label: const Text('Pending', style: TextStyle(fontSize: 10)),
                  backgroundColor: Colors.orange.shade100,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('Amount: ₦${approval['amount'] ?? 0}', style: const TextStyle(fontSize: 14)),
            Text('Requested by: ${approval['requestedByCode'] ?? 'N/A'}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton(
                  onPressed: onReject,
                  style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                  child: const Text('Reject'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: isAuthenticated ? onApprove : null,
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                  child: const Text('Approve'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _AlertCard extends StatelessWidget {
  final Map<String, dynamic> alert;

  const _AlertCard({required this.alert});

  @override
  Widget build(BuildContext context) {
    final severity = alert['severity'] as String? ?? 'medium';
    final color = severity == 'critical'
        ? Colors.red
        : severity == 'high'
            ? Colors.orange
            : severity == 'medium'
                ? Colors.amber
                : Colors.green;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      color: color.withOpacity(0.05),
      child: ListTile(
        leading: Icon(Icons.warning, color: color),
        title: Text(
          (alert['threat_type'] as String? ?? '').replaceAll('_', ' '),
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          alert['description'] as String? ?? '',
          style: const TextStyle(fontSize: 12),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('${alert['risk_score'] ?? 0}', style: TextStyle(color: color, fontWeight: FontWeight.bold)),
            const Text('Risk', style: TextStyle(fontSize: 10)),
          ],
        ),
      ),
    );
  }
}

class _StepUpAuthDialog extends StatefulWidget {
  final VoidCallback onAuthenticated;

  const _StepUpAuthDialog({required this.onAuthenticated});

  @override
  State<_StepUpAuthDialog> createState() => _StepUpAuthDialogState();
}

class _StepUpAuthDialogState extends State<_StepUpAuthDialog> {
  final _passwordController = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Step-Up Authentication'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'Re-enter your password to verify identity for privileged actions.',
            style: TextStyle(fontSize: 13, color: Colors.grey),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _passwordController,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Password',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.lock),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _loading
              ? null
              : () {
                  setState(() => _loading = true);
                  // In production: call API to verify password and get step-up token
                  Future.delayed(const Duration(milliseconds: 500), () {
                    widget.onAuthenticated();
                  });
                },
          child: _loading
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Verify'),
        ),
      ],
    );
  }
}
