import 'package:flutter/material.dart';
import '../services/api_service.dart';

class KycVerificationScreen extends StatefulWidget {
  const KycVerificationScreen({super.key});
  @override
  State<KycVerificationScreen> createState() => _KycVerificationScreenState();
}

class _KycVerificationScreenState extends State<KycVerificationScreen> {
  final _api = ApiService();
  final _bvnController = TextEditingController();
  final _ninController = TextEditingController();
  bool _loading = false;
  Map<String, dynamic>? _kycStatus;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadKycStatus();
  }

  Future<void> _loadKycStatus() async {
    try {
      final status = await _api.getKycStatus();
      setState(() { _kycStatus = status; });
    } catch (e) {
      // Ignore — user may not have KYC yet
    }
  }

  Future<void> _submitKyc() async {
    if (_bvnController.text.isEmpty && _ninController.text.isEmpty) {
      setState(() { _error = 'Please enter BVN or NIN'; });
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      await _api.submitKycDocument(
        docType: _bvnController.text.isNotEmpty ? 'bvn' : 'nin',
        docNumber: _bvnController.text.isNotEmpty ? _bvnController.text : _ninController.text,
      );
      await _loadKycStatus();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('KYC submitted successfully')),
      );
    } catch (e) {
      setState(() { _error = e.toString(); });
    } finally {
      setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _kycStatus?['status'] as String? ?? 'not_submitted';
    final statusColor = status == 'verified' ? Colors.green
        : status == 'pending' ? Colors.orange
        : status == 'rejected' ? Colors.red
        : Colors.grey;

    return Scaffold(
      appBar: AppBar(title: const Text('KYC Verification')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Icon(
                      status == 'verified' ? Icons.verified_user : Icons.pending,
                      color: statusColor,
                      size: 32,
                    ),
                    const SizedBox(width: 12),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('KYC Status', style: TextStyle(fontWeight: FontWeight.bold)),
                        Text(
                          status.toUpperCase().replaceAll('_', ' '),
                          style: TextStyle(color: statusColor, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            if (status != 'verified') ...[
              Text('Submit KYC Documents', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              TextField(
                controller: _bvnController,
                keyboardType: TextInputType.number,
                maxLength: 11,
                decoration: const InputDecoration(
                  labelText: 'BVN (Bank Verification Number)',
                  prefixIcon: Icon(Icons.fingerprint),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              const Center(child: Text('OR', style: TextStyle(color: Colors.grey))),
              const SizedBox(height: 12),
              TextField(
                controller: _ninController,
                keyboardType: TextInputType.number,
                maxLength: 11,
                decoration: const InputDecoration(
                  labelText: 'NIN (National Identification Number)',
                  prefixIcon: Icon(Icons.badge),
                  border: OutlineInputBorder(),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _loading ? null : _submitKyc,
                  child: _loading
                      ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Submit KYC'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _bvnController.dispose();
    _ninController.dispose();
    super.dispose();
  }
}
