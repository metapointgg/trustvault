import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/summary_card.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();

  late Future<_DashboardData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_DashboardData> _load() async {
    final responses = await Future.wait<Map<String, dynamic>>([
      _apiClient.getApiHealth(),
      _apiClient.getDashboardSummary(),
      _apiClient.getLicenceStatus(),
      _apiClient.getArchiveStatus(),
    ]);
    return _DashboardData(
        health: responses[0],
        summary: responses[1],
        licence: responses[2],
        archive: responses[3]);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: FutureBuilder<_DashboardData>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return _ErrorState(
              message:
                  'Unable to connect to the TrustVault API. ${snapshot.error}',
              onRetry: () => setState(() => _future = _load()),
            );
          }

          final data = snapshot.data!;
          final summary = data.summary;
          final health = data.health;
          final licence = data.licence;
          final archive = data.archive;
          final components = health['components'] as Map<String, dynamic>? ??
              <String, dynamic>{};
          final database = components['database'] is Map<String, dynamic>
              ? components['database'] as Map<String, dynamic>
              : <String, dynamic>{};
          final storage = components['storage'] is Map<String, dynamic>
              ? components['storage'] as Map<String, dynamic>
              : <String, dynamic>{};

          return ListView(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('TrustVault',
                            style: Theme.of(context)
                                .textTheme
                                .displaySmall
                                ?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        Text(
                            'Secure evidence assurance for regulated customer records',
                            style: Theme.of(context).textTheme.titleMedium),
                      ],
                    ),
                  ),
                  FilledButton.icon(
                    onPressed: () => setState(() => _future = _load()),
                    icon: const Icon(Icons.refresh),
                    label: const Text('Refresh'),
                  ),
                ],
              ),
              const SizedBox(height: 32),
              LayoutBuilder(
                builder: (context, constraints) {
                  final cardWidth = constraints.maxWidth > 1200
                      ? 260.0
                      : constraints.maxWidth > 760
                          ? (constraints.maxWidth - 16) / 2
                          : constraints.maxWidth;
                  return Wrap(
                    spacing: 16,
                    runSpacing: 16,
                    children: [
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'API status',
                              value: _statusLabel(health['status']),
                              icon: Icons.api)),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Database',
                              value: _statusLabel(database['status']),
                              icon: Icons.storage)),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Storage',
                              value: _statusLabel(storage['status']),
                              icon: Icons.folder_outlined)),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Licence',
                              value: _licenceSummary(licence),
                              icon: Icons.key)),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Completeness',
                              value:
                                  '${summary['completeness_exception_count'] ?? 0} missing',
                              icon: Icons.rule_folder_outlined,
                              onTap: () => context.go('/completeness'))),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Extraction',
                              value:
                                  '${summary['extraction_index_entry_count'] ?? summary['fits_index_entry_count'] ?? 0} indexed',
                              icon: Icons.document_scanner_outlined,
                              onTap: () => context.go('/extraction'))),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Legal & retention',
                              value:
                                  '${summary['retention_issue_count'] ?? 0} flags',
                              icon: Icons.policy_outlined,
                              onTap: () => context.go('/retention'))),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Integrity',
                              value:
                                  '${summary['integrity_issue_count'] ?? 0} issues',
                              icon: Icons.verified_outlined,
                              onTap: () => context.go('/integrity'))),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Categorisation',
                              value:
                                  '${summary['categorisation_uncategorised_count'] ?? 0} uncategorised',
                              icon: Icons.category_outlined,
                              onTap: () => context.go('/categorisation'))),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Entities',
                              value:
                                  '${summary['entity_count'] ?? archive['entity_count'] ?? 0}',
                              icon: Icons.business)),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Evidence objects',
                              value:
                                  '${summary['evidence_object_count'] ?? archive['evidence_object_count'] ?? 0}',
                              icon: Icons.folder_copy)),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Current FITS archives',
                              value:
                                  '${summary['current_fits_container_count'] ?? archive['current_fits_container_count'] ?? 0}',
                              icon: Icons.data_object_outlined)),
                      SizedBox(
                          width: cardWidth,
                          child: SummaryCard(
                              title: 'Open jobs',
                              value:
                                  '${(summary['queued_jobs'] ?? 0) + (summary['running_jobs'] ?? 0)}',
                              icon: Icons.pending_actions)),
                    ],
                  );
                },
              ),
              const SizedBox(height: 32),
              _ConfigurationPanel(archive: archive, licence: licence),
            ],
          );
        },
      ),
    );
  }

  String _statusLabel(dynamic value) {
    final text = '${value ?? 'unknown'}';
    if (text.isEmpty || text == 'null') return 'Unknown';
    return text.substring(0, 1).toUpperCase() +
        text.substring(1).replaceAll('_', ' ');
  }

  String _licenceSummary(Map<String, dynamic> licence) {
    final state = _statusLabel(licence['state']);
    final expiry = licence['valid_until'];
    if (expiry == null || '$expiry'.isEmpty || '$expiry' == 'null')
      return state;
    return '$state · expires $expiry';
  }
}

class _ConfigurationPanel extends StatelessWidget {
  const _ConfigurationPanel({required this.archive, required this.licence});

  final Map<String, dynamic> archive;
  final Map<String, dynamic> licence;

  @override
  Widget build(BuildContext context) {
    final config = archive['configuration'] as Map<String, dynamic>? ??
        <String, dynamic>{};
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Archive configuration',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                Chip(label: Text('Source: ${config['source_folder'] ?? '-'}')),
                Chip(
                    label: Text(
                        'Containers: ${config['containers_folder'] ?? '-'}')),
                Chip(label: Text('Index: ${config['index_path'] ?? '-'}')),
                Chip(
                    label: Text('Exports: ${config['exports_folder'] ?? '-'}')),
              ],
            ),
            const SizedBox(height: 12),
            Text(
                'Licence: ${licence['customer_name'] ?? 'Unknown customer'} · ${licence['edition'] ?? '-'} · ${licence['message'] ?? '-'}'),
          ],
        ),
      ),
    );
  }
}

class _DashboardData {
  const _DashboardData(
      {required this.health,
      required this.summary,
      required this.licence,
      required this.archive});

  final Map<String, dynamic> health;
  final Map<String, dynamic> summary;
  final Map<String, dynamic> licence;
  final Map<String, dynamic> archive;
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48),
              const SizedBox(height: 16),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(onPressed: onRetry, child: const Text('Retry')),
            ],
          ),
        ),
      ),
    );
  }
}
