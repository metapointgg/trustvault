import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class CompletenessScreen extends StatefulWidget {
  const CompletenessScreen({super.key});

  @override
  State<CompletenessScreen> createState() => _CompletenessScreenState();
}

class _CompletenessScreenState extends State<CompletenessScreen> {
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
    final nextFuture = _apiClient.evaluateCompleteness(externalId);
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
          _Header(
            title: 'Completeness',
            subtitle: 'Required-evidence rules evaluated against the selected customer FITS archive manifest.',
            onRefresh: _load,
          ),
          const SizedBox(height: 24),
          Expanded(
            child: _future == null
                ? const Center(child: Text('Select a customer to run completeness.'))
                : FutureBuilder<Map<String, dynamic>>(
                    key: ValueKey('completeness-$_loadedFor'),
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                      if (snapshot.hasError) return Center(child: Text('Unable to load completeness: ${snapshot.error}'));
                      final data = snapshot.data ?? <String, dynamic>{};
                      final rows = (data['results'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
                      final score = data['score'] ?? 0;
                      final missing = rows.where((row) => row['status'] == 'missing').toList();
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              _ScoreCard(score: score),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Wrap(
                                  spacing: 8,
                                  runSpacing: 8,
                                  children: [
                                    Chip(label: Text('Required: ${data['required_count'] ?? rows.length}')),
                                    Chip(label: Text('Present: ${data['present_count'] ?? rows.length - missing.length}')),
                                    Chip(label: Text('Missing: ${data['missing_count'] ?? missing.length}')),
                                    Chip(label: Text('Ruleset: ${data['ruleset_id'] ?? '-'}')),
                                  ],
                                ),
                              ),
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
                                      DataColumn(label: Text('Status')),
                                      DataColumn(label: Text('Rule')),
                                      DataColumn(label: Text('Category')),
                                      DataColumn(label: Text('Document type')),
                                      DataColumn(label: Text('Matched evidence')),
                                      DataColumn(label: Text('Matched filename')),
                                    ],
                                    rows: rows.map((row) {
                                      final present = row['status'] == 'present';
                                      return DataRow(
                                        color: present ? null : WidgetStatePropertyAll(Theme.of(context).colorScheme.errorContainer.withValues(alpha: 0.35)),
                                        cells: [
                                          DataCell(_StatusPill(label: '${row['status'] ?? '-'}', positive: present)),
                                          DataCell(Text('${row['rule_key'] ?? '-'}')),
                                          DataCell(Text('${row['category'] ?? '-'}')),
                                          DataCell(Text('${row['document_type'] ?? '-'}')),
                                          DataCell(SelectableText('${row['matched_evidence_object_id'] ?? '-'}')),
                                          DataCell(Text('${row['matched_filename'] ?? '-'}')),
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
}

class _ScoreCard extends StatelessWidget {
  const _ScoreCard({required this.score});

  final dynamic score;

  @override
  Widget build(BuildContext context) {
    final numeric = score is num ? score.toInt() : int.tryParse('$score') ?? 0;
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: numeric == 100 ? scheme.primaryContainer : scheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('$numeric%', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
            const Text('Completeness'),
          ],
        ),
      ),
    );
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
        OutlinedButton.icon(onPressed: onRefresh, icon: const Icon(Icons.refresh), label: const Text('Run review')),
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
