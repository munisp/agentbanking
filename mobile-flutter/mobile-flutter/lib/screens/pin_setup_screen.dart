import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/primary_button.dart';

class PinSetupScreen extends StatefulWidget {
  final bool isChange;
  const PinSetupScreen({super.key, this.isChange = false});
  @override
  State<PinSetupScreen> createState() => _PinSetupScreenState();
}

class _PinSetupScreenState extends State<PinSetupScreen> {
  final _pinCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  final _oldPinCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  Future<void> _submit() async {
    if (_pinCtrl.text.length != 4) {
      setState(() => _error = 'PIN must be 4 digits');
      return;
    }
    if (_pinCtrl.text != _confirmCtrl.text) {
      setState(() => _error = 'PINs do not match');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      if (widget.isChange) {
        await ApiService.instance.changePin(
            oldPin: _oldPinCtrl.text, newPin: _pinCtrl.text);
      } else {
        await ApiService.instance.setPin(pin: _pinCtrl.text);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('PIN updated successfully')));
        Navigator.pop(context);
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _pinCtrl.dispose(); _confirmCtrl.dispose(); _oldPinCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.isChange ? 'Change PIN' : 'Set PIN')),
    body: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (widget.isChange) ...[
          TextField(controller: _oldPinCtrl,
              decoration: const InputDecoration(labelText: 'Current PIN'),
              keyboardType: TextInputType.number, maxLength: 4, obscureText: true),
          const SizedBox(height: 12),
        ],
        TextField(controller: _pinCtrl,
            decoration: const InputDecoration(labelText: 'New PIN (4 digits)'),
            keyboardType: TextInputType.number, maxLength: 4, obscureText: true),
        const SizedBox(height: 12),
        TextField(controller: _confirmCtrl,
            decoration: const InputDecoration(labelText: 'Confirm New PIN'),
            keyboardType: TextInputType.number, maxLength: 4, obscureText: true),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: const TextStyle(color: Colors.red)),
        ],
        const Spacer(),
        PrimaryButton(label: 'Save PIN', onPressed: _loading ? null : _submit,
            loading: _loading),
      ]),
    ),
  );
}
