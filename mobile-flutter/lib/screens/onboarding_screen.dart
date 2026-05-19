import 'package:flutter/material.dart';
import '../services/api_service.dart';


class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});
  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _ctrl = PageController();
  int _page = 0;

  final _pages = const [
    _OnboardPage(
      icon: Icons.account_balance_wallet,
      title: 'Agency Banking Made Easy',
      body: 'Process cash-in, cash-out, bills, and transfers for your customers from one app.',
    ),
    _OnboardPage(
      icon: Icons.security,
      title: 'Secure & Compliant',
      body: 'CBN-licensed, end-to-end encrypted, and fully compliant with Nigerian financial regulations.',
    ),
    _OnboardPage(
      icon: Icons.offline_bolt,
      title: 'Works Offline',
      body: 'Continue serving customers even without internet. Transactions sync automatically when reconnected.',
    ),
  ];

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(child: Column(children: [
      Expanded(child: PageView.builder(
        controller: _ctrl,
        itemCount: _pages.length,
        onPageChanged: (i) => setState(() => _page = i),
        itemBuilder: (_, i) => _pages[i],
      )),
      Row(mainAxisAlignment: MainAxisAlignment.center, children: List.generate(
        _pages.length,
        (i) => AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          margin: const EdgeInsets.symmetric(horizontal: 4),
          width: _page == i ? 24 : 8,
          height: 8,
          decoration: BoxDecoration(
            color: _page == i ? Theme.of(context).colorScheme.primary : Colors.grey,
            borderRadius: BorderRadius.circular(4)),
        ),
      )),
      const SizedBox(height: 24),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: ElevatedButton(
          style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
          onPressed: () {
            if (_page < _pages.length - 1) {
              _ctrl.nextPage(duration: const Duration(milliseconds: 300), curve: Curves.ease);
            } else {
              Navigator.pushReplacementNamed(context, '/login');
            }
          },
          child: Text(_page < _pages.length - 1 ? 'Next' : 'Get Started'),
        ),
      ),
      const SizedBox(height: 16),
    ])),
  );
}

class _OnboardPage extends StatelessWidget {
  final IconData icon;
  final String title;
  final String body;
  const _OnboardPage({required this.icon, required this.title, required this.body});
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(32),
    child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Icon(icon, size: 100, color: Theme.of(context).colorScheme.primary),
      const SizedBox(height: 32),
      Text(title, style: Theme.of(context).textTheme.headlineSmall,
          textAlign: TextAlign.center),
      const SizedBox(height: 16),
      Text(body, style: Theme.of(context).textTheme.bodyMedium,
          textAlign: TextAlign.center),
    ]),
  );
}
