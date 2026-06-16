import 'package:flutter/material.dart';
import '../services/api_service.dart';

class TransferTrackingScreen extends StatefulWidget {
  final String? transactionId;
  const TransferTrackingScreen({super.key, this.transactionId});
  @override
  State<TransferTrackingScreen> createState() => _TransferTrackingScreenState();
}

class _TransferTrackingScreenState extends State<TransferTrackingScreen> {
  Map<String, dynamic>? _tx;
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    if (widget.transactionId == null) {
      setState(() => _loading = false);
      return;
    }
    try {
      final data = await ApiService.instance.getTransaction(widget.transactionId!);
      setState(() { _tx = data; _loading = false; });
    } catch (_) { setState(() => _loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final steps = ['Initiated', 'Processing', 'Completed'];
    final statusMap = {'pending': 0, 'processing': 1, 'completed': 2, 'failed': 2};
    final currentStep = statusMap[_tx?['status']] ?? 0;
    final isFailed = _tx?['status'] == 'failed';

    return Scaffold(
      appBar: AppBar(title: const Text('Transfer Tracking')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _tx == null
              ? const Center(child: Text('Transaction not found'))
              : Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Card(child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('₦${((_tx!['amount'] ?? 0) / 100.0).toStringAsFixed(2)}',
                            style: Theme.of(context).textTheme.headlineMedium),
                        Text(_tx!['narration'] ?? ''),
                        const SizedBox(height: 8),
                        Text('Ref: ${_tx!['reference'] ?? ''}',
                            style: const TextStyle(color: Colors.grey, fontSize: 12)),
                      ]),
                    )),
                    const SizedBox(height: 24),
                    Stepper(
                      currentStep: currentStep,
                      steps: steps.asMap().entries.map((e) => Step(
                        title: Text(e.value),
                        isActive: e.key <= currentStep,
                        state: isFailed && e.key == currentStep
                            ? StepState.error
                            : e.key < currentStep
                                ? StepState.complete
                                : StepState.indexed,
                        content: const SizedBox.shrink(),
                      )).toList(),
                    ),
                    if (isFailed) ...[
                      const SizedBox(height: 16),
                      Text('Error: ${_tx!['error_message'] ?? 'Transfer failed'}',
                          style: const TextStyle(color: Colors.red)),
                    ],
                  ]),
                ),
    );
  }
}
