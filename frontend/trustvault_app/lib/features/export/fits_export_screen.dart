import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/trustvault_api_client.dart';

class FitsExportScreen extends StatefulWidget {
  const FitsExportScreen({super.key});

  @override
  State<FitsExportScreen> createState() => _FitsExportScreenState();
}

class _FitsExportScreenState extends State<FitsExportScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _customersFuture;

  @override
  void initState() {
    super.initState();
    _customersFuture = _apiClient.getCustomers();
  }

  Future<void> _downloadCurrentFits(Map<String, dynamic> customer) async {
    final containerVersionId = customer['current_container_version_id'];
    if (containerVersionId == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Customer has no current FITS archive.')));
      return;
    }
    final uri = Uri.parse(_apiClient.fitsDownloadUrl('$containerVersionId'));
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to open $uri')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Export', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Export is FITS-native. The current FITS archive is the source-of-truth evidence object.'),
          const SizedBox(height: 24),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _customersFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(child: Text('Unable to load customers: ${snapshot.error}'));
                }
                final customers = snapshot.data ?? <dynamic>[];
                if (customers.isEmpty) {
                  return const Center(child: Text('No customers available for export.'));
                }
                return ListView.separated(
                  itemCount: customers.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final customer = customers[index] as Map<String, dynamic>;
                    final hasFits = customer['has_current_fits_container'] == true;
                    return Card(
                      child: ListTile(
                        leading: Icon(hasFits ? Icons.data_object : Icons.warning_amber_outlined),
                        title: Text('${customer['display_name']}'),
                        subtitle: SelectableText(
                          'External ID: ${customer['external_id']}\n'
                          'Current version: ${customer['current_container_version_number'] ?? '-'}\n'
                          'Storage URI: ${customer['current_container_storage_uri'] ?? '-'}',
                        ),
                        trailing: FilledButton.icon(
                          onPressed: hasFits ? () => _downloadCurrentFits(customer) : null,
                          icon: const Icon(Icons.download),
                          label: const Text('Download FITS'),
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
