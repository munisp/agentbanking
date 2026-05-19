import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../services/api_service.dart';


class CashInScreen extends StatelessWidget {
  const CashInScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('CashInScreen'.replaceAll('Screen', '').replaceAllMapped(RegExp(r'[A-Z]'), (m) => ' ${m[0]}').trim())),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('CashInScreen', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 24),
            ElevatedButton(onPressed: () => context.pop(), child: const Text('Back')),
          ],
        ),
      ),
    );
  }
}
