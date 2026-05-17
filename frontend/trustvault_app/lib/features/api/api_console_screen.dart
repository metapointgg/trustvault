import 'dart:convert';

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class ApiConsoleScreen extends StatefulWidget {
  const ApiConsoleScreen({super.key});

  @override
  State<ApiConsoleScreen> createState() => _ApiConsoleScreenState();
}

class _ApiConsoleScreenState extends State<ApiConsoleScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _queryController = TextEditingController(
    text: 'Show me all onboarding documentation for high risk clients in Guernsey.',
  );
  bool _useSelectedCustomer = false;
  bool _loading = false;
  Map<String, dynamic>? _result;
  String? _error;
  late Future<Map<String, dynamic>> _archiveStatusFuture;
  late Future<Map<String, dynamic>> _scenarioFuture;

  @override
  void initState() {
    super.initState();
    _archiveStatusFuture = _apiClient.getArchiveStatus();
    _scenarioFuture = _apiClient.getQueryScenarios();
  }

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _run({required bool execute}) async {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final entity = _useSelectedCustomer ? SelectedCustomerController.externalId : null;
      final result = execute
          ? await _apiClient.executeQuery(query: query, entityExternalId: entity)
          : await _apiClient.interpretQuery(query: query, entityExternalId: entity);
      if (!mounted) return;
      setState(() {
        _result = result;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _loading = false;
      });
    }
  }

  void _setExample(String example) {
    final cleaned = example
        .replaceFirst('Use TrustVault to interpret this query but do not execute it: ', '')
        .replaceFirst('Use TrustVault to interpret this query: ', '')
        .replaceFirst('Use TrustVault to execute this query: ', '')
        .replaceFirst('Use TrustVault to execute this query for CUST-000001: ', '')
        .replaceFirst('Use TrustVault to ', '');
    setState(() {
      _queryController.text = cleaned;
      _useSelectedCustomer = example.contains('CUST-000001') || example.toLowerCase().contains('selected customer');
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('API and query console', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text('Run archive-wide searches, selected-customer FITS searches, query interpretation checks and natural-language execution tests.'),
                  ],
                ),
              ),
              OutlinedButton.icon(
                onPressed: () {
                  setState(() {
                    _archiveStatusFuture = _apiClient.getArchiveStatus();
                    _scenarioFuture = _apiClient.getQueryScenarios();
                  });
                },
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 180,
            child: Row(
              children: [
                Expanded(child: _ArchiveStatusCard(future: _archiveStatusFuture)),
                const SizedBox(width: 16),
                Expanded(child: _ScenarioPicker(future: _scenarioFuture, onSelected: _setExample)),
              ],
            ),
          ),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _queryController,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'TrustVault query',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _useSelectedCustomer,
                    onChanged: (value) => setState(() => _useSelectedCustomer = value),
                    title: const Text('Run in selected-customer scope'),
                    subtitle: Text('Selected customer: ${SelectedCustomerController.displayLabel}. Off means archive-wide/index-backed search.'),
                  ),
                  Row(
                    children: [
                      FilledButton.icon(
                        onPressed: _loading ? null : () => _run(execute: false),
                        icon: const Icon(Icons.psychology_alt_outlined),
                        label: const Text('Interpret only'),
                      ),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                        onPressed: _loading ? null : () => _run(execute: true),
                        icon: const Icon(Icons.play_arrow),
                        label: const Text('Execute'),
                      ),
                      if (_loading) ...[
                        const SizedBox(width: 16),
                        const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          if (_error != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            ),
          Expanded(
            child: _result == null
                ? const Center(child: Text('Interpret or execute a TrustVault query to view structured output.'))
                : _QueryResultView(result: _result!),
          ),
        ],
      ),
    );
  }
}

class _ArchiveStatusCard extends StatelessWidget {
  const _ArchiveStatusCard({required this.future});

  final Future<Map<String, dynamic>> future;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<Map<String, dynamic>>(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError) return Text('Archive status unavailable: ${snapshot.error}');
            final data = snapshot.data ?? <String, dynamic>{};
            final config = data['configuration'] as Map<String, dynamic>? ?? <String, dynamic>{};
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Archive status', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    Chip(label: Text('Entities: ${data['entity_count'] ?? 0}')),
                    Chip(label: Text('Containers: ${data['current_fits_container_count'] ?? 0}')),
                    Chip(label: Text('Indexed objects: ${data['fits_index_entry_count'] ?? 0}')),
                  ],
                ),
                const SizedBox(height: 8),
                Expanded(
                  child: SingleChildScrollView(
                    child: Text(
                      'Source: ${config['source_folder'] ?? '-'}\nContainers: ${config['containers_folder'] ?? '-'}\nIndex: ${config['index_path'] ?? '-'}\nExports: ${config['exports_folder'] ?? '-'}',
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ScenarioPicker extends StatelessWidget {
  const _ScenarioPicker({required this.future, required this.onSelected});

  final Future<Map<String, dynamic>> future;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<Map<String, dynamic>>(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError) return Text('Scenarios unavailable: ${snapshot.error}');
            final scenarios = (snapshot.data?['scenarios'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Scenario library', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Expanded(
                  child: ListView.builder(
                    itemCount: scenarios.length,
                    itemBuilder: (context, index) {
                      final group = scenarios[index];
                      final examples = (group['examples'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();
                      return ExpansionTile(
                        dense: true,
                        title: Text('${group['group']}'),
                        children: examples.map((example) {
                          return ListTile(
                            dense: true,
                            title: Text('$example'),
                            onTap: () => onSelected('$example'),
                          );
                        }).toList(),
                      );
                    },
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _QueryResultView extends StatelessWidget {
  const _QueryResultView({required this.result});

  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final structured = result['structured_query'] as Map<String, dynamic>?;
    final executionSource = result['execution_source'];
    final executionResult = result['result'] as Map<String, dynamic>?;
    final rows = (executionResult?['results'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (structured != null) ...[
              Text('Structured query', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(label: Text('Scope: ${structured['scope']}')),
                  Chip(label: Text('Capability: ${structured['capability']}')),
                  Chip(label: Text('Execute with: ${structured['execute_with']}')),
                  if (structured['snapshot_id'] != null) Chip(label: Text('Snapshot: ${structured['snapshot_id']}')),
                  if (structured['risk_rating'] != null) Chip(label: Text('Risk: ${structured['risk_rating']}')),
                  if (structured['jurisdiction'] != null) Chip(label: Text('Jurisdiction: ${structured['jurisdiction']}')),
                ],
              ),
              const SizedBox(height: 12),
            ],
            if (executionSource != null) ...[
              Text('Execution source: $executionSource'),
              const SizedBox(height: 8),
              Text('Result count: ${executionResult?['result_count'] ?? rows.length}'),
              const SizedBox(height: 12),
            ],
            Expanded(
              child: rows.isEmpty
                  ? SingleChildScrollView(child: SelectableText(const JsonEncoder.withIndent('  ').convert(result)))
                  : ListView.separated(
                      itemCount: rows.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (context, index) {
                        final row = rows[index] as Map<String, dynamic>;
                        return ListTile(
                          leading: const Icon(Icons.article_outlined),
                          title: Text('${row['filename'] ?? row['entity_external_id'] ?? row['run_id'] ?? 'Result'}'),
                          subtitle: SelectableText(row.entries.map((entry) => '${entry.key}: ${entry.value}').join('\n')),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
