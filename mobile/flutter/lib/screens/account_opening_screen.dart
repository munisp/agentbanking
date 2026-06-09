import 'package:flutter/material.dart';

class AccountOpeningScreen extends StatefulWidget {
  const AccountOpeningScreen({super.key});

  @override
  State<AccountOpeningScreen> createState() => _AccountOpeningScreenState();
}

class _AccountOpeningScreenState extends State<AccountOpeningScreen> {
  final _formKey = GlobalKey<FormState>();
  bool _isLoading = false;
  String _accountType = 'savings';

  Future<void> _submitApplication() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    // API call to submit account opening application
    await Future.delayed(const Duration(seconds: 2));
    setState(() => _isLoading = false);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Account application submitted')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Open New Account')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  DropdownButtonFormField<String>(
                    value: _accountType,
                    decoration: const InputDecoration(labelText: 'Account Type'),
                    items: const [
                      DropdownMenuItem(value: 'savings', child: Text('Savings')),
                      DropdownMenuItem(value: 'current', child: Text('Current')),
                      DropdownMenuItem(value: 'fixed', child: Text('Fixed Deposit')),
                    ],
                    onChanged: (v) => setState(() => _accountType = v ?? 'savings'),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    decoration: const InputDecoration(labelText: 'Full Name'),
                    validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    decoration: const InputDecoration(labelText: 'BVN'),
                    keyboardType: TextInputType.number,
                    validator: (v) => v == null || v.length != 11 ? 'Must be 11 digits' : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    decoration: const InputDecoration(labelText: 'Phone Number'),
                    keyboardType: TextInputType.phone,
                    validator: (v) => v == null || v.isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    decoration: const InputDecoration(labelText: 'Email'),
                    keyboardType: TextInputType.emailAddress,
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: _submitApplication,
                    child: const Text('Submit Application'),
                  ),
                ],
              ),
            ),
    );
  }
}
