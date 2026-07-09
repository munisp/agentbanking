import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';


class SupportScreen extends StatelessWidget {
  const SupportScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Help & Support')),
    body: ListView(children: [
      const Padding(
        padding: EdgeInsets.all(16),
        child: Text('How can we help you?',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
      ),
      ListTile(
        leading: const Icon(Icons.chat_bubble_outline),
        title: const Text('Live Chat'),
        subtitle: const Text('Chat with support agent'),
        onTap: () => Navigator.pushNamed(context, '/live-chat'),
      ),
      ListTile(
        leading: const Icon(Icons.phone),
        title: const Text('Call Support'),
        subtitle: const Text('+234 800 54LINK'),
        onTap: () => launchUrl(Uri.parse('tel:+23480054LINK')),
      ),
      ListTile(
        leading: const Icon(Icons.email_outlined),
        title: const Text('Email Support'),
        subtitle: const Text('support@54link.ng'),
        onTap: () => launchUrl(Uri.parse('mailto:support@54link.ng')),
      ),
      const Divider(),
      ListTile(
        leading: const Icon(Icons.help_outline),
        title: const Text('FAQ'),
        onTap: () => Navigator.pushNamed(context, '/faq'),
      ),
      ListTile(
        leading: const Icon(Icons.article_outlined),
        title: const Text('Terms of Service'),
        onTap: () => launchUrl(Uri.parse('https://54link.ng/terms')),
      ),
      ListTile(
        leading: const Icon(Icons.privacy_tip_outlined),
        title: const Text('Privacy Policy'),
        onTap: () => launchUrl(Uri.parse('https://54link.ng/privacy')),
      ),
    ]),
  );
}
