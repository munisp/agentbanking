import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../services/api_service.dart';


class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('HistoryScreen'.replaceAll('Screen', '').replaceAllMapped(RegExp(r'[A-Z]'), (m) => ' ${m[0]}').trim())),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('HistoryScreen', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 24),
            ElevatedButton(onPressed: () => context.pop(), child: const Text('Back')),
          ],
        ),
      ),
    );
  }
}
