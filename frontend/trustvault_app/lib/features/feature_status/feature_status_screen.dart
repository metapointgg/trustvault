import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class FeatureStatusScreen extends StatefulWidget {
  const FeatureStatusScreen(
      {super.key,
      required this.title,
      required this.description,
      required this.loader});

  final String title;
  final String description;
  final Future<Map<String, dynamic>> Function(TrustVaultApiClient apiClient)
      loader;

  @override
  State<FeatureStatusScreen> createState() => _FeatureStatusScreenState();
}

class _FeatureStatusScreenState extends State<FeatureStatusScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.loader(_apiClient);
  }

  void _refresh() {
    setState(() => _future = widget.loader(_apiClient));
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
                    Text(widget.title,
                        style: Theme.of(context)
                            .textTheme
                            .displaySmall
                            ?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    Text(widget.description),
                  ],
                ),
              ),
              OutlinedButton.icon(
                  onPressed: _refresh,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 24),
          Expanded(
            child: FutureBuilder<Map<String, dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done)
                  return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError)
                  return Center(
                      child: Text(
                          'Unable to load ${widget.title}: ${snapshot.error}'));
                final data = snapshot.data ?? <String, dynamic>{};
                if (data.containsKey('components'))
                  return _HealthStatusView(data: data);
                return _GenericStatusView(data: data);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _HealthStatusView extends StatelessWidget {
  const _HealthStatusView({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final components =
        data['components'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final componentRows = components.entries.map((entry) {
      final details = entry.value is Map<String, dynamic>
          ? entry.value as Map<String, dynamic>
          : <String, dynamic>{'status': entry.value};
      return _ComponentStatus(
          name: entry.key,
          status: '${details['status'] ?? 'unknown'}',
          details: details);
    }).toList();

    final overall = '${data['status'] ?? 'unknown'}';
    final healthy =
        overall == 'ok' || overall == 'healthy' || overall == 'ready';
    final configuration = <String, dynamic>{
      'Application': data['app'],
      'Environment': data['environment'],
      'Storage provider': data['storage_provider'],
      'Queue provider': data['queue_provider'],
      'AI provider': data['ai_provider'],
      'OCR provider': data['ocr_provider'],
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
                child: _OverallStatusCard(status: overall, healthy: healthy)),
            const SizedBox(width: 16),
            Expanded(child: _ConfigurationCard(configuration: configuration)),
          ],
        ),
        const SizedBox(height: 16),
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final crossAxisCount = constraints.maxWidth > 1200
                  ? 4
                  : constraints.maxWidth > 820
                      ? 3
                      : 2;
              return GridView.builder(
                itemCount: componentRows.length,
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: crossAxisCount,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                  childAspectRatio: 1.55,
                ),
                itemBuilder: (context, index) => componentRows[index],
              );
            },
          ),
        ),
      ],
    );
  }
}

class _OverallStatusCard extends StatelessWidget {
  const _OverallStatusCard({required this.status, required this.healthy});

  final String status;
  final bool healthy;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: healthy ? scheme.primaryContainer : scheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            Icon(healthy ? Icons.check_circle_outline : Icons.error_outline,
                size: 42,
                color: healthy
                    ? scheme.onPrimaryContainer
                    : scheme.onErrorContainer),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Overall status',
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(status.toUpperCase(),
                    style: Theme.of(context)
                        .textTheme
                        .headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w800)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ConfigurationCard extends StatelessWidget {
  const _ConfigurationCard({required this.configuration});

  final Map<String, dynamic> configuration;

  @override
  Widget build(BuildContext context) {
    final rows =
        configuration.entries.where((entry) => entry.value != null).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Runtime configuration',
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            Wrap(
                spacing: 8,
                runSpacing: 8,
                children: rows
                    .map((entry) =>
                        Chip(label: Text('${entry.key}: ${entry.value}')))
                    .toList()),
          ],
        ),
      ),
    );
  }
}

class _ComponentStatus extends StatelessWidget {
  const _ComponentStatus(
      {required this.name, required this.status, required this.details});

  final String name;
  final String status;
  final Map<String, dynamic> details;

  @override
  Widget build(BuildContext context) {
    final positive = _isPositive(status);
    final neutral = _isNeutral(status);
    final scheme = Theme.of(context).colorScheme;
    final background = positive
        ? scheme.primaryContainer
        : neutral
            ? scheme.secondaryContainer
            : scheme.errorContainer;
    final foreground = positive
        ? scheme.onPrimaryContainer
        : neutral
            ? scheme.onSecondaryContainer
            : scheme.onErrorContainer;
    final extra = Map<String, dynamic>.from(details)..remove('status');
    final visibleExtra = extra.entries
        .where((entry) => entry.value != null && '${entry.value}'.isNotEmpty)
        .toList();
    final description = _descriptionFor(name, status);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                      color: background,
                      borderRadius: BorderRadius.circular(12)),
                  child: Icon(_iconFor(name), color: foreground),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(_label(name),
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 4),
                      _StatusPill(
                          status: _statusLabel(status),
                          positive: positive,
                          neutral: neutral),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(description, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 8),
            Expanded(
              child: visibleExtra.isEmpty
                  ? Text(
                      positive || neutral
                          ? 'No errors reported.'
                          : 'No additional diagnostic details reported.',
                      style: Theme.of(context).textTheme.bodySmall)
                  : SingleChildScrollView(
                      child: Text(
                          visibleExtra
                              .map((entry) =>
                                  '${_label(entry.key)}: ${entry.value}')
                              .join('\n'),
                          style: Theme.of(context).textTheme.bodySmall),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  bool _isPositive(String value) => [
        'ok',
        'healthy',
        'ready',
        'connected',
        'available',
        'success'
      ].contains(value.toLowerCase());
  bool _isNeutral(String value) => [
        'database-backed',
        'polled',
        'disabled_by_default',
        'sidecar_or_metadata_first',
        'none'
      ].contains(value.toLowerCase());

  String _statusLabel(String value) => value.replaceAll('_', ' ');

  String _descriptionFor(String name, String status) {
    switch (name.toLowerCase()) {
      case 'api':
        return 'Confirms the TrustVault API process is running and responding.';
      case 'database':
        return 'Confirms the application can connect to the TrustVault database.';
      case 'storage':
        return 'Confirms configured evidence storage is reachable. Errors are shown below when present.';
      case 'queue':
        return status == 'database-backed'
            ? 'Jobs are currently queued through the TrustVault database.'
            : 'Confirms the configured background job queue provider.';
      case 'worker':
        return status == 'polled'
            ? 'Background work is picked up by the worker using job-table polling.'
            : 'Confirms the background worker heartbeat/status.';
      case 'ai':
        return status == 'disabled_by_default'
            ? 'AI is available only where explicitly enabled or requested.'
            : 'Reports the configured AI provider status.';
      case 'ocr':
        return status == 'sidecar_or_metadata_first'
            ? 'Text extraction currently uses sidecar/search metadata first.'
            : 'Reports the configured OCR provider status.';
      default:
        return 'Reports health for this TrustVault component.';
    }
  }

  IconData _iconFor(String name) {
    switch (name.toLowerCase()) {
      case 'api':
        return Icons.api_outlined;
      case 'database':
        return Icons.storage_outlined;
      case 'storage':
        return Icons.folder_outlined;
      case 'queue':
        return Icons.queue_outlined;
      case 'worker':
        return Icons.engineering_outlined;
      case 'ai':
        return Icons.psychology_alt_outlined;
      case 'ocr':
        return Icons.document_scanner_outlined;
      case 'auth':
        return Icons.admin_panel_settings_outlined;
      default:
        return Icons.health_and_safety_outlined;
    }
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill(
      {required this.status, required this.positive, required this.neutral});

  final String status;
  final bool positive;
  final bool neutral;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final background = positive
        ? scheme.primaryContainer
        : neutral
            ? scheme.secondaryContainer
            : scheme.errorContainer;
    final foreground = positive
        ? scheme.onPrimaryContainer
        : neutral
            ? scheme.onSecondaryContainer
            : scheme.onErrorContainer;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
          color: background, borderRadius: BorderRadius.circular(999)),
      child: Text(status,
          style: TextStyle(color: foreground, fontWeight: FontWeight.w700)),
    );
  }
}

class _GenericStatusView extends StatelessWidget {
  const _GenericStatusView({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final entries = data.entries.toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: ListView.separated(
          itemCount: entries.length,
          separatorBuilder: (_, __) => const Divider(),
          itemBuilder: (context, index) {
            final entry = entries[index];
            return ListTile(
                title: Text(_label(entry.key),
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: SelectableText('${entry.value}'));
          },
        ),
      ),
    );
  }
}

String _label(String value) {
  if (value.isEmpty) return value;
  return value
      .replaceAll('_', ' ')
      .split(' ')
      .where((part) => part.isNotEmpty)
      .map((part) => part.substring(0, 1).toUpperCase() + part.substring(1))
      .join(' ');
}
