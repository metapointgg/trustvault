import 'package:flutter/material.dart';

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
    final health = await _apiClient.getHealth();
    final summary = await _apiClient.getDashboardSummary();
    final licence = await _apiClient.getLicenceStatus();
    return _DashboardData(health: health, summary: summary, licence: licence);
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
              message: 'Unable to connect to the TrustVault API. ${snapshot.error}',
              onRetry: () => setState(() => _future = _load()),
            );
          }

          final data = snapshot.data!;
          final summary = data.summary;
          final health = data.health;
          final licence = data.licence;

          return ListView(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('TrustVault', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        Text(
                          'Secure evidence assurance for regulated customer records',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
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
              Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  SizedBox(
                    width: 260,
                    child: SummaryCard(
                      title: 'API status',
                      value: '${health['status'] ?? 'unknown'}',
                      icon: Icons.api,
                    ),
                  ),
                  SizedBox(
                    width: 260,
                    child: SummaryCard(
                      title: 'Database',
                      value: '${health['database'] ?? 'unknown'}',
                      icon: Icons.storage,
                    ),
                  ),
                  SizedBox(
                    width: 260,
                    child: SummaryCard(
                      title: 'Licence',
                      value: '${licence['state'] ?? 'unknown'}',
                      icon: Icons.key,
                    ),
                  ),
                  SizedBox(
                    width: 260,
                    child: SummaryCard(
                      title: 'Entities',
                      value: '${summary['entity_count'] ?? 0}',
                      icon: Icons.business,
                    ),
                  ),
                  SizedBox(
                    width: 260,
                    child: SummaryCard(
                      title: 'Evidence objects',
                      value: '${summary['evidence_object_count'] ?? 0}',
                      icon: Icons.folder_copy,
                    ),
                  ),
                  SizedBox(
                    width: 260,
                    child: SummaryCard(
                      title: 'Queued jobs',
                      value: '${summary['queued_jobs'] ?? 0}',
                      icon: Icons.pending_actions,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 32),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Production build status', style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 12),
                      const Text('This first TrustVault build establishes the production-shaped shell: FastAPI, worker, PostgreSQL, audit, licence status, local storage abstraction and Flutter Web UI.'),
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

class _DashboardData {
  const _DashboardData({required this.health, required this.summary, required this.licence});

  final Map<String, dynamic> health;
  final Map<String, dynamic> summary;
  final Map<String, dynamic> licence;
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
