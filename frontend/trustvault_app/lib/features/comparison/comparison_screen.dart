import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/customer_selector_card.dart';
import '../../shared/selected_customer.dart';

class ComparisonScreen extends StatefulWidget {
  const ComparisonScreen({super.key});

  @override
  State<ComparisonScreen> createState() => _ComparisonScreenState();
}

class _ComparisonScreenState extends State<ComparisonScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _queryController =
      TextEditingController(text: 'passport');
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
    _queryController.dispose();
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
    final query = _queryController.text.trim();
    final nextFuture = _apiClient.compareFitsVsDatabase(externalId,
        query: query.isEmpty ? null : query);
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
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Comparison',
                        style: Theme.of(context)
                            .textTheme
                            .displaySmall
                            ?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text(
                        'Compares one customer FITS archive with database and index projections.'),
                  ],
                ),
              ),
              SizedBox(
                width: 240,
                child: TextField(
                  controller: _queryController,
                  decoration: const InputDecoration(
                      labelText: 'Search parity query',
                      border: OutlineInputBorder()),
                  onSubmitted: (_) => _load(),
                ),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                  onPressed: _load,
                  icon: const Icon(Icons.compare_arrows),
                  label: const Text('Compare')),
            ],
          ),
          const SizedBox(height: 16),
          CustomerSelectorCard(
            title: 'Customer to compare',
            subtitle:
                'The comparison checks this customer FITS archive against the database/index projections.',
            onChanged: (_) => _load(),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: _future == null
                ? const Center(
                    child: Text(
                        'Select a customer to compare FITS and projections.'))
                : FutureBuilder<Map<String, dynamic>>(
                    key: ValueKey('comparison-$_loadedFor'),
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done)
                        return const Center(child: CircularProgressIndicator());
                      if (snapshot.hasError)
                        return Center(
                            child:
                                Text('Unable to compare: ${snapshot.error}'));
                      final data = snapshot.data ?? <String, dynamic>{};
                      final checks =
                          (data['checks'] as List<dynamic>? ?? <dynamic>[])
                              .cast<Map<String, dynamic>>();
                      final failures =
                          checks.where((row) => row['status'] == 'fail').length;
                      final warnings = checks
                          .where((row) => row['status'] == 'warning')
                          .length;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              _StatusChip(
                                  label: 'Checks: ${checks.length}',
                                  good: true),
                              _StatusChip(
                                  label: 'Failures: $failures',
                                  good: failures == 0),
                              _StatusChip(
                                  label: 'Warnings: $warnings',
                                  good: warnings == 0),
                              Chip(
                                  label: Text(
                                      'Container: ${data['container_version_id'] ?? '-'}')),
                            ],
                          ),
                          const SizedBox(height: 16),
                          Expanded(
                            child: Card(
                              child: SingleChildScrollView(
                                scrollDirection: Axis.horizontal,
                                child: DataTable(
                                  columns: const [
                                    DataColumn(label: Text('Status')),
                                    DataColumn(label: Text('Check')),
                                    DataColumn(label: Text('Details')),
                                  ],
                                  rows: checks.map((row) {
                                    final status = '${row['status'] ?? '-'}';
                                    final good = status == 'pass';
                                    return DataRow(
                                      color: good
                                          ? null
                                          : WidgetStatePropertyAll(
                                              Theme.of(context)
                                                  .colorScheme
                                                  .errorContainer
                                                  .withValues(alpha: 0.35)),
                                      cells: [
                                        DataCell(_StatusPill(
                                            label: status, positive: good)),
                                        DataCell(Text('${row['name'] ?? '-'}')),
                                        DataCell(SizedBox(
                                            width: 520,
                                            child:
                                                SelectableText(_details(row)))),
                                      ],
                                    );
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

  String _details(Map<String, dynamic> row) {
    final copy = Map<String, dynamic>.from(row)
      ..remove('name')
      ..remove('status');
    if (copy.isEmpty) return '-';
    return copy.entries
        .map((entry) => '${entry.key}: ${entry.value}')
        .join('\n');
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
      avatar: Icon(good ? Icons.check_circle : Icons.error,
          size: 18, color: good ? scheme.primary : scheme.error),
      label: Text(label),
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
      child: Text(label,
          style: TextStyle(
              color: positive
                  ? scheme.onPrimaryContainer
                  : scheme.onErrorContainer)),
    );
  }
}
