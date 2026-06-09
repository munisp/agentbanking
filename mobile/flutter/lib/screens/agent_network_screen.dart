import 'package:flutter/material.dart';

class AgentNetworkScreen extends StatefulWidget {
  const AgentNetworkScreen({super.key});

  @override
  State<AgentNetworkScreen> createState() => _AgentNetworkScreenState();
}

class _AgentNetworkScreenState extends State<AgentNetworkScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _agents = [];

  @override
  void initState() {
    super.initState();
    _loadAgentNetwork();
  }

  Future<void> _loadAgentNetwork() async {
    setState(() => _isLoading = true);
    await Future.delayed(const Duration(seconds: 1));
    setState(() {
      _agents = List.generate(20, (i) => {
        return {
          'name': 'Agent ${i + 1}',
          'code': 'AG-${1000 + i}',
          'status': i % 5 == 0 ? 'inactive' : 'active',
          'territory': ['Lagos', 'Abuja', 'Kano', 'Port Harcourt'][i % 4],
          'transactions_today': (50 + i * 10),
        };
      });
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Agent Network'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {},
          ),
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: () {},
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadAgentNetwork,
              child: ListView.builder(
                itemCount: _agents.length,
                itemBuilder: (context, index) {
                  final agent = _agents[index];
                  return ListTile(
                    leading: CircleAvatar(
                      backgroundColor: agent['status'] == 'active'
                          ? Colors.green
                          : Colors.grey,
                      child: Text(agent['name'].substring(0, 1)),
                    ),
                    title: Text(agent['name']),
                    subtitle: Text('${agent['code']} • ${agent['territory']}'),
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('${agent['transactions_today']} txns'),
                        Text(
                          agent['status'].toUpperCase(),
                          style: TextStyle(
                            fontSize: 10,
                            color: agent['status'] == 'active'
                                ? Colors.green
                                : Colors.grey,
                          ),
                        ),
                      ],
                    ),
                    onTap: () {},
                  );
                },
              ),
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
        child: const Icon(Icons.person_add),
      ),
    );
  }
}
