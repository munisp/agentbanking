import 'package:flutter/material.dart';
import '../services/api_service.dart';

class VoiceCommandPosScreen extends StatefulWidget {
  const VoiceCommandPosScreen({super.key});
  @override
  State<VoiceCommandPosScreen> createState() => _VoiceCommandPosScreenState();
}

class _VoiceCommandPosScreenState extends State<VoiceCommandPosScreen> {
  bool _isListening = false;
  String _commandText = '';
  String _selectedLanguage = 'english';
  Map<String, dynamic>? _parsedIntent;
  bool _confirmationPending = false;
  String _resultMessage = '';
  bool _processing = false;

  final _languages = {
    'english': 'English',
    'yoruba': 'Yoruba',
    'hausa': 'Hausa',
    'igbo': 'Igbo',
    'pidgin': 'Nigerian Pidgin',
  };

  Future<void> _processCommand() async {
    if (_commandText.isEmpty) return;
    setState(() => _processing = true);
    try {
      final result = await ApiService.instance.post(
        '/api/trpc/voiceCommandPos.processCommand',
        body: {
          'json': {
            'rawText': _commandText,
            'language': _selectedLanguage,
            'idempotencyKey': 'IDK-${DateTime.now().millisecondsSinceEpoch}',
          }
        },
      );
      final data = result?['result']?['data']?['json'];
      if (data != null) {
        setState(() {
          _parsedIntent = data;
          _confirmationPending = true;
          _processing = false;
        });
      }
    } catch (e) {
      setState(() {
        _resultMessage = 'Error: $e';
        _processing = false;
      });
    }
  }

  Future<void> _confirmAndExecute() async {
    if (_parsedIntent == null) return;
    setState(() => _processing = true);
    try {
      final result = await ApiService.instance.post(
        '/api/trpc/voiceCommandPos.confirmAndExecute',
        body: {
          'json': {
            'intent': _parsedIntent!['intent'],
            'amount': _parsedIntent!['amount'],
            'phone': _parsedIntent!['phone'],
            'idempotencyKey': 'IDK-${DateTime.now().millisecondsSinceEpoch}',
          }
        },
      );
      setState(() {
        _resultMessage = 'Transaction completed: ${result?['result']?['data']?['json']?['reference'] ?? 'Success'}';
        _confirmationPending = false;
        _parsedIntent = null;
        _processing = false;
      });
    } catch (e) {
      setState(() {
        _resultMessage = 'Error: $e';
        _processing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Voice Command POS')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Language selector
            const Text('Language', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: _languages.entries.map((e) {
                return ChoiceChip(
                  label: Text(e.value),
                  selected: _selectedLanguage == e.key,
                  onSelected: (_) => setState(() => _selectedLanguage = e.key),
                );
              }).toList(),
            ),
            const SizedBox(height: 16),

            // Voice input area
            Card(
              color: _isListening ? Colors.green[50] : null,
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    Icon(
                      _isListening ? Icons.mic : Icons.mic_none,
                      size: 48,
                      color: _isListening ? Colors.green : Colors.grey,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _isListening ? 'Listening...' : 'Tap to speak',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      '"Send five thousand naira to 08012345678"',
                      style: TextStyle(color: Colors.grey[600], fontSize: 13),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Listen button
            ElevatedButton.icon(
              onPressed: () => setState(() => _isListening = !_isListening),
              icon: Icon(_isListening ? Icons.mic_off : Icons.mic),
              label: Text(_isListening ? 'Stop Listening' : 'Start Voice Command'),
              style: ElevatedButton.styleFrom(
                backgroundColor: _isListening ? Colors.red : Colors.blue,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
            const SizedBox(height: 12),

            // Manual text input
            TextField(
              decoration: InputDecoration(
                labelText: 'Or type command',
                hintText: 'e.g., send 5000 to 08012345678',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onChanged: (v) => setState(() => _commandText = v),
            ),
            const SizedBox(height: 8),

            if (_commandText.isNotEmpty)
              ElevatedButton(
                onPressed: _processing ? null : _processCommand,
                child: _processing
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Process Command'),
              ),

            // Two-step confirmation
            if (_confirmationPending && _parsedIntent != null) ...[
              const SizedBox(height: 16),
              Card(
                color: Colors.amber[50],
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Confirm Transaction',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 8),
                      Text('Type: ${_parsedIntent!['intent'] ?? 'unknown'}'),
                      Text('Amount: ₦${_parsedIntent!['amount'] ?? 0}'),
                      if (_parsedIntent!['phone'] != null)
                        Text('Phone: ${_parsedIntent!['phone']}'),
                      Text('Confidence: ${((_parsedIntent!['confidence'] ?? 0) * 100).toInt()}%'),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: ElevatedButton(
                              onPressed: _processing ? null : _confirmAndExecute,
                              style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                              child: const Text('Confirm & Execute',
                                  style: TextStyle(color: Colors.white)),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => setState(() {
                                _confirmationPending = false;
                                _parsedIntent = null;
                              }),
                              child: const Text('Cancel'),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],

            // Result
            if (_resultMessage.isNotEmpty) ...[
              const SizedBox(height: 16),
              Card(
                color: _resultMessage.startsWith('Error') ? Colors.red[50] : Colors.green[50],
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(
                        _resultMessage.startsWith('Error')
                            ? Icons.error_outline
                            : Icons.check_circle,
                        color: _resultMessage.startsWith('Error') ? Colors.red : Colors.green,
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_resultMessage)),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
