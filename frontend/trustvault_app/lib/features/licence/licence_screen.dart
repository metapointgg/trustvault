import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class LicenceScreen extends StatefulWidget {
  const LicenceScreen({super.key});

  @override
  State<LicenceScreen> createState() => _LicenceScreenState();
}

class _LicenceScreenState extends State<LicenceScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<Map<String, dynamic>> _future;
  bool _uploading = false;
  String? _message;
  String? _error;

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getLicenceStatus();
  }

  Future<void> _uploadLicence() async {
    setState(() {
      _uploading = true;
      _message = null;
      _error = null;
    });
    try {
      final picked = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: const ['json'], withData: true);
      if (picked == null || picked.files.isEmpty) {
        setState(() => _uploading = false);
        return;
      }
      final file = picked.files.single;
      final bytes = file.bytes;
      if (bytes == null) throw StateError('No file bytes were returned by the browser picker.');
      final result = await _apiClient.uploadLicenceFile(filename: file.name, bytes: bytes);
      if (!mounted) return;
      setState(() {
        _message = 'Licence applied: ${result['state']} · ${result['customer_name'] ?? 'Unknown customer'}';
        _future = Future<Map<String, dynamic>>.value(result);
        _uploading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _uploading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return Center(child: Text('Unable to load licence status: ${snapshot.error}'));

          final licence = snapshot.data ?? <String, dynamic>{};
          final modules = (licence['modules'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();
          final validUntil = licence['valid_until'];

          return ListView(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Licence', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        const Text('Review the active TrustVault deployment entitlement and apply replacement licence files.'),
                      ],
                    ),
                  ),
                  OutlinedButton.icon(onPressed: () => setState(() => _future = _apiClient.getLicenceStatus()), icon: const Icon(Icons.refresh), label: const Text('Refresh')),
                  const SizedBox(width: 12),
                  FilledButton.icon(
                    onPressed: _uploading ? null : _uploadLicence,
                    icon: _uploading ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.upload_file),
                    label: Text(_uploading ? 'Applying...' : 'Upload licence'),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (_message != null) _Banner(message: _message!, positive: true),
              if (_error != null) _Banner(message: _error!, positive: false),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.key_outlined),
                        title: Text('${licence['customer_name'] ?? 'Unknown customer'}'),
                        subtitle: Text('${licence['message'] ?? ''}'),
                        trailing: _StatusPill(label: '${licence['state'] ?? 'unknown'}'),
                      ),
                      const Divider(height: 32),
                      _DetailRow(label: 'Licence ID', value: '${licence['licence_id'] ?? '-'}'),
                      _DetailRow(label: 'Edition', value: '${licence['edition'] ?? '-'}'),
                      _DetailRow(label: 'Expiry date', value: validUntil == null ? '-' : '$validUntil'),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Licensed modules', style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 16),
                      if (modules.isEmpty)
                        const Text('No licensed modules reported by the current licence file.')
                      else
                        Wrap(spacing: 8, runSpacing: 8, children: modules.map((module) => Chip(label: Text('$module'))).toList()),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final positive = label.toLowerCase() == 'valid';
    final warning = label.toLowerCase() == 'grace';
    final scheme = Theme.of(context).colorScheme;
    final background = positive ? scheme.primaryContainer : warning ? scheme.secondaryContainer : scheme.errorContainer;
    final foreground = positive ? scheme.onPrimaryContainer : warning ? scheme.onSecondaryContainer : scheme.onErrorContainer;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(999)),
      child: Text(label, style: TextStyle(color: foreground, fontWeight: FontWeight.w700)),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.message, required this.positive});

  final String message;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: positive ? scheme.primaryContainer : scheme.errorContainer, borderRadius: BorderRadius.circular(12)),
      child: Text(message, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(width: 140, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700))),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
