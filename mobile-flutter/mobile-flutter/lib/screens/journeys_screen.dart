import 'package:flutter/material.dart';
import '../services/api_service.dart';

class JourneysScreen extends StatefulWidget {
  const JourneysScreen({super.key});
  @override
  State<JourneysScreen> createState() => _JourneysScreenState();
}

class _JourneysScreenState extends State<JourneysScreen> {
  final _api = ApiService();
  List<dynamic> _journeys = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadJourneys();
  }

  Future<void> _loadJourneys() async {
    try {
      // Customer journeys are fetched from the loyalty/CDP system
      final profile = await _api.getProfile();
      // Simulate journeys from profile data
      setState(() {
        _journeys = [
          {
            'id': '1',
            'title': 'Onboarding Journey',
            'description': 'Complete your agent profile and first transaction',
            'steps': 5,
            'completed': profile['onboardingStep'] ?? 3,
            'status': 'active',
          },
          {
            'id': '2',
            'title': 'Gold Agent Path',
            'description': 'Reach Gold tier with 500 transactions',
            'steps': 10,
            'completed': 7,
            'status': 'active',
          },
          {
            'id': '3',
            'title': 'Compliance Certification',
            'description': 'Complete AML/KYC training modules',
            'steps': 3,
            'completed': 3,
            'status': 'completed',
          },
        ];
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Journeys')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error'))
              : RefreshIndicator(
                  onRefresh: _loadJourneys,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _journeys.length,
                    itemBuilder: (context, i) {
                      final j = _journeys[i];
                      final progress = (j['completed'] as int) / (j['steps'] as int);
                      final isCompleted = j['status'] == 'completed';
                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(
                                    isCompleted ? Icons.check_circle : Icons.route,
                                    color: isCompleted ? Colors.green : Colors.blue,
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(j['title'] as String, style: const TextStyle(fontWeight: FontWeight.bold)),
                                  ),
                                  if (isCompleted)
                                    const Chip(
                                      label: Text('Done', style: TextStyle(fontSize: 11)),
                                      backgroundColor: Colors.green,
                                      labelStyle: TextStyle(color: Colors.white),
                                    ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(j['description'] as String, style: const TextStyle(color: Colors.grey, fontSize: 13)),
                              const SizedBox(height: 12),
                              LinearProgressIndicator(
                                value: progress,
                                backgroundColor: Colors.grey[200],
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  isCompleted ? Colors.green : Colors.blue,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${j['completed']} / ${j['steps']} steps',
                                style: const TextStyle(fontSize: 12, color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}
