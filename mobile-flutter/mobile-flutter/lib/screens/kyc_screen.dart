import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';
import '../widgets/primary_button.dart';

/// KYC verification screen — NIN, BVN, ID document upload
class KycScreen extends StatefulWidget {
  const KycScreen({super.key});

  @override
  State<KycScreen> createState() => _KycScreenState();
}

class _KycScreenState extends State<KycScreen> {
  final _formKey = GlobalKey<FormState>();
  final _ninController = TextEditingController();
  final _bvnController = TextEditingController();
  File? _idFront;
  File? _idBack;
  File? _selfie;
  bool _loading = false;
  String? _error;
  int _step = 0; // 0=BVN/NIN, 1=Documents, 2=Selfie, 3=Review

  final _picker = ImagePicker();

  @override
  void dispose() {
    _ninController.dispose();
    _bvnController.dispose();
    super.dispose();
  }

  Future<void> _pickImage(String type) async {
    final source = type == 'selfie' ? ImageSource.camera : ImageSource.gallery;
    final picked = await _picker.pickImage(source: source, imageQuality: 85);
    if (picked == null) return;
    setState(() {
      switch (type) {
        case 'front':
          _idFront = File(picked.path);
          break;
        case 'back':
          _idBack = File(picked.path);
          break;
        case 'selfie':
          _selfie = File(picked.path);
          break;
      }
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _loading = true; _error = null; });
    try {
      await ApiService.instance.submitKyc(
        nin: _ninController.text.trim(),
        bvn: _bvnController.text.trim(),
        idFront: _idFront,
        idBack: _idBack,
        selfie: _selfie,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('KYC submitted — under review (24–48 hrs)')),
        );
        Navigator.of(context).pop();
      }
    } catch (e) {
      setState(() { _error = e.toString(); });
    } finally {
      if (mounted) setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('KYC Verification')),
      body: Stepper(
        currentStep: _step,
        onStepContinue: () {
          if (_step < 3) setState(() => _step++);
          else _submit();
        },
        onStepCancel: () {
          if (_step > 0) setState(() => _step--);
        },
        steps: [
          Step(
            title: const Text('Identity Numbers'),
            isActive: _step >= 0,
            content: Form(
              key: _formKey,
              child: Column(children: [
                TextFormField(
                  controller: _ninController,
                  decoration: const InputDecoration(labelText: 'NIN (11 digits)'),
                  keyboardType: TextInputType.number,
                  maxLength: 11,
                  validator: (v) => (v?.length == 11) ? null : 'Enter valid 11-digit NIN',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _bvnController,
                  decoration: const InputDecoration(labelText: 'BVN (11 digits)'),
                  keyboardType: TextInputType.number,
                  maxLength: 11,
                  validator: (v) => (v?.length == 11) ? null : 'Enter valid 11-digit BVN',
                ),
              ]),
            ),
          ),
          Step(
            title: const Text('ID Document'),
            isActive: _step >= 1,
            content: Column(children: [
              _ImagePickerTile(
                label: 'Front of ID',
                file: _idFront,
                onTap: () => _pickImage('front'),
              ),
              const SizedBox(height: 12),
              _ImagePickerTile(
                label: 'Back of ID',
                file: _idBack,
                onTap: () => _pickImage('back'),
              ),
            ]),
          ),
          Step(
            title: const Text('Selfie'),
            isActive: _step >= 2,
            content: _ImagePickerTile(
              label: 'Take a selfie',
              file: _selfie,
              onTap: () => _pickImage('selfie'),
            ),
          ),
          Step(
            title: const Text('Review & Submit'),
            isActive: _step >= 3,
            content: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_error != null)
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                Text('NIN: ${_ninController.text}'),
                Text('BVN: ${_bvnController.text}'),
                Text('ID Front: ${_idFront != null ? "Uploaded" : "Missing"}'),
                Text('ID Back: ${_idBack != null ? "Uploaded" : "Missing"}'),
                Text('Selfie: ${_selfie != null ? "Uploaded" : "Missing"}'),
                const SizedBox(height: 16),
                if (_loading) const CircularProgressIndicator(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ImagePickerTile extends StatelessWidget {
  final String label;
  final File? file;
  final VoidCallback onTap;

  const _ImagePickerTile({required this.label, this.file, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 120,
        decoration: BoxDecoration(
          border: Border.all(color: Colors.grey),
          borderRadius: BorderRadius.circular(8),
          image: file != null
              ? DecorationImage(image: FileImage(file!), fit: BoxFit.cover)
              : null,
        ),
        child: file == null
            ? Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.camera_alt, size: 40, color: Colors.grey),
                Text(label, style: const TextStyle(color: Colors.grey)),
              ])
            : null,
      ),
    );
  }
}
