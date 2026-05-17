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

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getLicenceStatus();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Unable to load licence status: ${snapshot.error}'));
          }

          final licence = snapshot.data ?? <String, dynamic>{};
          final modules = (licence['modules'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();

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
                        const Text('Review the active TrustVault deployment entitlement.'),
                      ],
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => setState(() => _future = _apiClient.getLicenceStatus()),
                    icon: const Icon(Icons.refresh),
                    label: const Text('Refresh'),
                  ),
                ],
              ),
              const SizedBox(height: 24),
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
                        trailing: Chip(label: Text('${licence['state'] ?? 'unknown'}')),
                      ),
                      const Divider(height: 32),
                      _DetailRow(label: 'Licence ID', value: '${licence['licence_id'] ?? '-'}'),
                      _DetailRow(label: 'Edition', value: '${licence['edition'] ?? '-'}'),
                      _DetailRow(label: 'Valid until', value: '${licence['valid_until'] ?? '-'}'),
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
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: modules.map((module) => Chip(label: Text('$module'))).toList(),
                      ),
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
