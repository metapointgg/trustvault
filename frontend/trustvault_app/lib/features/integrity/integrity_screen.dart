import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class IntegrityScreen extends StatefulWidget {
  const IntegrityScreen({super.key});

  @override
  State<IntegrityScreen> createState() => _IntegrityScreenState();
}

class _IntegrityScreenState extends State<IntegrityScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  Future<Map<String, dynamic>>? _future;
  String? _loadedFor;

  @override
  void initState() {
    super.initState();
    SelectedCustomerController.selected.addListener(_load);
    _load();
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_load);
    super.dispose();
  }

  void _load() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId == null || externalId.isEmpty) {
      setState(() {
        _future = null;
        _loadedFor = null;
      });
      return;
    }
    final nextFuture = _apiClient.getEntityIntegrity(externalId);
    setState(() {
      _future = nextFuture;
      _loadedFor = externalId;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Header(title: 'Integrity', subtitle: 'Fixity and structural validation for the selected customer FITS archive.', onRefresh: _load),
          const SizedBox(height: 24),
          Expanded(
            child: _future == null
                ? const Center(child: Text('Select a customer to validate integrity.'))
                : FutureBuilder<Map<String, dynamic>>(
                    key: ValueKey('integrity-$_loadedFor'),
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                      if (snapshot.hasError) return Center(child: Text('Unable to load integrity report: ${snapshot.error}'));
                      final data = snapshot.data ?? <String, dynamic>{};
                      final payloads = (data['payload_results'] as List<dynamic>? ?? data['payloads'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
                      final failedPayloads = payloads.where((row) => row['status'] != 'valid' && row['valid'] != true).toList();
                      final missingHdus = (data['missing_required_hdus'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();
                      final overall = '${data['overall_status'] ?? data['status'] ?? '-'}';
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              _StatusChip(label: 'Overall: $overall', good: overall == 'valid' || overall == 'success'),
                              _StatusChip(label: 'Container hash: ${_yesNo(data['container_hash_matches'])}', good: data['container_hash_matches'] != false),
                              _StatusChip(label: 'FITS opened: ${_yesNo(data['fits_opened'])}', good: data['fits_opened'] != false),
                              _StatusChip(label: 'Missing HDUs: ${missingHdus.length}', good: missingHdus.isEmpty),
                              _StatusChip(label: 'Payloads: ${payloads.length}', good: failedPayloads.isEmpty),
                              _StatusChip(label: 'Failed payloads: ${failedPayloads.length}', good: failedPayloads.isEmpty),
                            ],
                          ),
                          const SizedBox(height: 16),
                          Expanded(
                            child: Card(
                              child: failedPayloads.isEmpty
                                  ? Center(
                                      child: Column(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(Icons.verified, size: 56, color: Theme.of(context).colorScheme.primary),
                                          const SizedBox(height: 12),
                                          Text('All payloads passed integrity validation', style: Theme.of(context).textTheme.titleLarge),
                                          const SizedBox(height: 8),
                                          Text('Validated payloads: ${payloads.length}'),
                                        ],
                                      ),
                                    )
                                  : SingleChildScrollView(
                                      scrollDirection: Axis.horizontal,
                                      child: DataTable(
                                        columns: const [
                                          DataColumn(label: Text('Payload')),
                                          DataColumn(label: Text('Filename')),
                                          DataColumn(label: Text('Status')),
                                          DataColumn(label: Text('Expected SHA-256')),
                                          DataColumn(label: Text('Actual SHA-256')),
                                        ],
                                        rows: failedPayloads.map((row) {
                                          return DataRow(cells: [
                                            DataCell(Text('${row['hdu_name'] ?? row['payload_hdu'] ?? '-'}')),
                                            DataCell(Text('${row['filename'] ?? '-'}')),
                                            DataCell(Text('${row['status'] ?? row['valid'] ?? '-'}')),
                                            DataCell(SelectableText('${row['expected_sha256'] ?? row['sha256'] ?? '-'}')),
                                            DataCell(SelectableText('${row['actual_sha256'] ?? '-'}')),
                                          ]);
                                        }).toList(),
                                      ),
                                    ),
                            ),
                          ),
                        ],
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  String _yesNo(dynamic value) {
    if (value == true) return 'yes';
    if (value == false) return 'no';
    return '-';
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.title, required this.subtitle, required this.onRefresh});

  final String title;
  final String subtitle;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Text(subtitle),
              const SizedBox(height: 8),
              Text('Customer: ${SelectedCustomerController.displayLabel}', style: Theme.of(context).textTheme.titleSmall),
            ],
          ),
        ),
        OutlinedButton.icon(onPressed: onRefresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
      ],
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.good});

  final String label;
  final bool good;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Chip(
      avatar: Icon(good ? Icons.check_circle : Icons.error, size: 18, color: good ? scheme.primary : scheme.error),
      label: Text(label),
    );
  }
}
