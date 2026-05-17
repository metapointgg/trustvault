import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class RetentionScreen extends StatefulWidget {
  const RetentionScreen({super.key});

  @override
  State<RetentionScreen> createState() => _RetentionScreenState();
}

class _RetentionScreenState extends State<RetentionScreen> {
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
        _loadedFor = null;
        _future = null;
      });
      return;
    }
    final nextFuture = _apiClient.getEntityRetention(externalId);
    setState(() {
      _loadedFor = externalId;
      _future = nextFuture;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Header(title: 'Retention', subtitle: 'Retention, sensitivity and legal-hold state from the selected customer FITS manifest.', onRefresh: _load),
          const SizedBox(height: 24),
          Expanded(
            child: _future == null
                ? const Center(child: Text('Select a customer to view retention data.'))
                : FutureBuilder<Map<String, dynamic>>(
                    key: ValueKey('retention-$_loadedFor'),
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (snapshot.hasError) {
                        return Center(child: Text('Unable to load retention report: ${snapshot.error}'));
                      }
                      final evidence = _evidenceRows(snapshot.data ?? <String, dynamic>{});
                      if (evidence.isEmpty) {
                        return const Center(child: Text('No retention evidence rows found.'));
                      }
                      final legalHoldCount = evidence.where((row) => '${row['legal_hold_status']}'.toLowerCase() != 'none').length;
                      final deletionEligibleCount = evidence.where((row) => row['deletion_eligible'] == true).length;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              Chip(label: Text('Evidence rows: ${evidence.length}')),
                              Chip(label: Text('Legal holds: $legalHoldCount')),
                              Chip(label: Text('Deletion eligible: $deletionEligibleCount')),
                            ],
                          ),
                          const SizedBox(height: 16),
                          Expanded(
                            child: Card(
                              child: SingleChildScrollView(
                                scrollDirection: Axis.horizontal,
                                child: SingleChildScrollView(
                                  child: DataTable(
                                    columns: const [
                                      DataColumn(label: Text('Filename')),
                                      DataColumn(label: Text('Category')),
                                      DataColumn(label: Text('Document type')),
                                      DataColumn(label: Text('Retention class')),
                                      DataColumn(label: Text('Retention until')),
                                      DataColumn(label: Text('Legal hold')),
                                      DataColumn(label: Text('Deletion eligible')),
                                    ],
                                    rows: evidence.map((row) {
                                      return DataRow(
                                        cells: [
                                          DataCell(SizedBox(width: 260, child: Text('${row['filename'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                          DataCell(Text('${row['category'] ?? '-'}')),
                                          DataCell(Text('${row['document_type'] ?? '-'}')),
                                          DataCell(Text('${row['retention_class'] ?? '-'}')),
                                          DataCell(Text('${row['retention_until'] ?? '-'}')),
                                          DataCell(_StatusPill(label: '${row['legal_hold_status'] ?? 'none'}', positive: '${row['legal_hold_status']}'.toLowerCase() == 'none')),
                                          DataCell(_StatusPill(label: row['deletion_eligible'] == true ? 'Yes' : 'No', positive: row['deletion_eligible'] != true)),
                                        ],
                                      );
                                    }).toList(),
                                  ),
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

  List<Map<String, dynamic>> _evidenceRows(Map<String, dynamic> data) {
    final entities = data['entities'] as List<dynamic>? ?? <dynamic>[];
    if (entities.isEmpty) return <Map<String, dynamic>>[];
    final evidence = entities.first['evidence'] as List<dynamic>? ?? <dynamic>[];
    return evidence.cast<Map<String, dynamic>>();
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

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.label, required this.positive});

  final String label;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        color: positive ? scheme.primaryContainer : scheme.errorContainer,
      ),
      child: Text(label, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
    );
  }
}
