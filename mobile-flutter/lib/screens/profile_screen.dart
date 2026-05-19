import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});
  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  Map<String, dynamic>? _profile;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await ApiService.instance.getProfile();
      setState(() { _profile = data; _loading = false; });
    } catch (_) {
      setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Profile')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _profile == null
              ? const Center(child: Text('Failed to load profile'))
              : ListView(padding: const EdgeInsets.all(16), children: [
                  CircleAvatar(
                    radius: 48,
                    backgroundImage: _profile!['avatar_url'] != null
                        ? NetworkImage(_profile!['avatar_url'])
                        : null,
                    child: _profile!['avatar_url'] == null
                        ? Text((_profile!['name'] ?? 'U')[0].toUpperCase(),
                            style: const TextStyle(fontSize: 36))
                        : null,
                  ),
                  const SizedBox(height: 16),
                  Center(child: Text(_profile!['name'] ?? '',
                      style: Theme.of(context).textTheme.headlineSmall)),
                  Center(child: Text(_profile!['phone'] ?? '',
                      style: Theme.of(context).textTheme.bodyMedium)),
                  const Divider(height: 32),
                  _InfoTile(label: 'Email', value: _profile!['email'] ?? 'Not set'),
                  _InfoTile(label: 'Agent ID', value: _profile!['agent_id'] ?? ''),
                  _InfoTile(label: 'KYC Status', value: _profile!['kyc_status'] ?? 'Pending'),
                  _InfoTile(label: 'Account Tier', value: _profile!['tier'] ?? '1'),
                  _InfoTile(label: 'Member Since',
                      value: _profile!['created_at'] != null
                          ? DateTime.fromMillisecondsSinceEpoch(
                              _profile!['created_at']).toString().split(' ')[0]
                          : ''),
                ]),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final String label;
  final String value;
  const _InfoTile({required this.label, required this.value});
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label, style: const TextStyle(color: Colors.grey)),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w500)),
      ]),
    );
  }
}
