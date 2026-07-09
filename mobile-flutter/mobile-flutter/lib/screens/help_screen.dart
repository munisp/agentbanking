import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';


class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  static const _faqs = [
    {
      'q': 'How do I process a Cash In transaction?',
      'a': 'Tap "Cash In" on the home screen, enter the customer\'s phone number or account, enter the amount, and confirm with your PIN.',
    },
    {
      'q': 'What should I do if a transaction fails?',
      'a': 'Check your network connection. If the issue persists, tap "Reversal" to reverse the transaction and contact support.',
    },
    {
      'q': 'How do I request a float top-up?',
      'a': 'Go to Float Balance → Request Top-Up. Enter the amount and submit. Your supervisor will approve within 30 minutes.',
    },
    {
      'q': 'How do I verify a customer\'s KYC?',
      'a': 'Tap "KYC Verify", enter the customer\'s BVN or NIN, and follow the on-screen prompts to capture their biometrics.',
    },
    {
      'q': 'What are my daily transaction limits?',
      'a': 'Limits depend on your agent tier. Bronze: ₦50K/day, Silver: ₦200K/day, Gold: ₦500K/day, Platinum: ₦1M/day.',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Help & Support')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Contact Support Card
          Card(
            color: Theme.of(context).colorScheme.primaryContainer,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Contact Support', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => launchUrl(Uri.parse('tel:+2348001234567')),
                          icon: const Icon(Icons.phone),
                          label: const Text('Call'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => launchUrl(Uri.parse('https://wa.me/2348001234567')),
                          icon: const Icon(Icons.chat),
                          label: const Text('WhatsApp'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => launchUrl(Uri.parse('mailto:support@54link.com')),
                          icon: const Icon(Icons.email),
                          label: const Text('Email'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text('Frequently Asked Questions', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ..._faqs.map((faq) => Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ExpansionTile(
              title: Text(faq['q']!, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: Text(faq['a']!, style: const TextStyle(fontSize: 13, color: Colors.grey)),
                ),
              ],
            ),
          )),
          const SizedBox(height: 16),
          // Useful Links
          Text('Resources', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ListTile(
            leading: const Icon(Icons.book),
            title: const Text('Agent Training Manual'),
            trailing: const Icon(Icons.open_in_new),
            onTap: () => launchUrl(Uri.parse('https://54link.com/docs/agent-manual')),
          ),
          ListTile(
            leading: const Icon(Icons.policy),
            title: const Text('CBN Agency Banking Guidelines'),
            trailing: const Icon(Icons.open_in_new),
            onTap: () => launchUrl(Uri.parse('https://cbn.gov.ng/guidelines')),
          ),
          ListTile(
            leading: const Icon(Icons.info),
            title: const Text('App Version'),
            subtitle: const Text('54Link POS v4.2.1'),
            onTap: () {},
          ),
        ],
      ),
    );
  }
}
