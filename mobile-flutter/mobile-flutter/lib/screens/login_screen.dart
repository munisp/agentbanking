import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';


class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _agentCodeCtrl = TextEditingController();
  final _pinCtrl = TextEditingController();
  final _terminalCtrl = TextEditingController(text: 'PAX-A920-001');

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.point_of_sale, size: 64, color: Color(0xFF1A56DB)),
              const SizedBox(height: 16),
              Text('54Link POS', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 32),
              TextField(controller: _agentCodeCtrl, decoration: const InputDecoration(labelText: 'Agent Code', prefixIcon: Icon(Icons.person))),
              const SizedBox(height: 16),
              TextField(controller: _pinCtrl, obscureText: true, decoration: const InputDecoration(labelText: 'PIN', prefixIcon: Icon(Icons.lock)), keyboardType: TextInputType.number, maxLength: 6),
              const SizedBox(height: 16),
              TextField(controller: _terminalCtrl, decoration: const InputDecoration(labelText: 'Terminal ID', prefixIcon: Icon(Icons.devices))),
              const SizedBox(height: 24),
              if (auth.error != null) Text(auth.error!, style: const TextStyle(color: Colors.red)),
              ElevatedButton(
                onPressed: auth.isLoading ? null : () async {
                  final ok = await ref.read(authProvider.notifier).login(agentCode: _agentCodeCtrl.text, pin: _pinCtrl.text, terminalId: _terminalCtrl.text);
                  if (ok && context.mounted) context.go('/dashboard');
                },
                child: auth.isLoading ? const CircularProgressIndicator(color: Colors.white) : const Text('Login'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
