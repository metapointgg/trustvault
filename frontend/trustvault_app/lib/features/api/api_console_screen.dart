import 'dart:convert';

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/customer_selector_card.dart';
import '../../shared/selected_customer.dart';

class ApiConsoleScreen extends StatefulWidget {
  const ApiConsoleScreen({super.key});

  @override
  State<ApiConsoleScreen> createState() => _ApiConsoleScreenState();
}

class _ApiConsoleScreenState extends State<ApiConsoleScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _queryController = TextEditingController(
    text:
        'Show me all onboarding documentation for high risk clients in Guernsey.',
  );
  bool _useSelectedCustomer = false;
  bool _includeAiSummary = true;
  String _interpretationMode = 'auto';
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
      final entity =
          _useSelectedCustomer ? SelectedCustomerController.externalId : null;
      final result = execute
          ? await _apiClient.executeQuery(
              query: query,
              entityExternalId: entity,
              mode: _interpretationMode,
              includeAiSummary: _includeAiSummary,
            )
          : await _apiClient.interpretQuery(
              query: query,
              entityExternalId: entity,
              mode: _interpretationMode);
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
        .replaceFirst(
            'Use TrustVault to interpret this query but do not execute it: ',
            '')
        .replaceFirst('Use TrustVault to interpret this query: ', '')
        .replaceFirst('Use TrustVault to execute this query: ', '')
        .replaceFirst(
            'Use TrustVault to execute this query for CUST-000001: ', '')
        .replaceFirst('Use TrustVault to ', '');
    setState(() {
      _queryController.text = cleaned;
      _useSelectedCustomer = example.contains('CUST-000001') ||
          example.toLowerCase().contains('selected customer');
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
                    Text('API and query console',
                        style: Theme.of(context)
                            .textTheme
                            .displaySmall
                            ?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text(
                        'Run archive-wide searches, selected-customer FITS searches, AI-assisted interpretation checks and natural-language execution tests.'),
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
                Expanded(
                    child: _ArchiveStatusCard(future: _archiveStatusFuture)),
                const SizedBox(width: 16),
                Expanded(
                    child: _ScenarioPicker(
                        future: _scenarioFuture, onSelected: _setExample)),
              ],
            ),
          ),
          const SizedBox(height: 20),
          if (_useSelectedCustomer) ...[
            CustomerSelectorCard(
              title: 'Selected-customer query context',
              subtitle:
                  'Used when the query should run against one customer FITS archive instead of the cross-archive index.',
            ),
            const SizedBox(height: 20),
          ],
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
                        border: OutlineInputBorder()),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          value: _useSelectedCustomer,
                          onChanged: (value) =>
                              setState(() => _useSelectedCustomer = value),
                          title: const Text('Run in selected-customer scope'),
                          subtitle: Text(_useSelectedCustomer
                              ? 'Selected customer: ${SelectedCustomerController.displayLabel}'
                              : 'Archive-wide / index-backed search'),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          value: _includeAiSummary,
                          onChanged: (value) =>
                              setState(() => _includeAiSummary = value),
                          title: const Text('Request AI summary'),
                          subtitle: const Text(
                              'Adds include_ai_summary=true when executing a query.'),
                        ),
                      ),
                      const SizedBox(width: 16),
                      SizedBox(
                        width: 260,
                        child: DropdownButtonFormField<String>(
                          value: _interpretationMode,
                          decoration: const InputDecoration(
                              labelText: 'Interpretation mode',
                              border: OutlineInputBorder()),
                          items: const [
                            DropdownMenuItem(
                                value: 'auto', child: Text('Auto')),
                            DropdownMenuItem(
                                value: 'deterministic',
                                child: Text('Deterministic')),
                            DropdownMenuItem(
                                value: 'ai', child: Text('AI assisted')),
                          ],
                          onChanged: (value) => setState(
                              () => _interpretationMode = value ?? 'auto'),
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      FilledButton.icon(
                          onPressed:
                              _loading ? null : () => _run(execute: false),
                          icon: const Icon(Icons.psychology_alt_outlined),
                          label: const Text('Interpret only')),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                          onPressed:
                              _loading ? null : () => _run(execute: true),
                          icon: const Icon(Icons.play_arrow),
                          label: const Text('Execute')),
                      if (_loading) ...[
                        const SizedBox(width: 16),
                        const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2)),
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
                    child: Text(_error!,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error)))),
          Expanded(
            child: _result == null
                ? const Center(
                    child: Text(
                        'Interpret or execute a TrustVault query to view structured output.'))
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
            if (snapshot.connectionState != ConnectionState.done)
              return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError)
              return Text('Archive status unavailable: ${snapshot.error}');
            final data = snapshot.data ?? <String, dynamic>{};
            final config = data['configuration'] as Map<String, dynamic>? ??
                <String, dynamic>{};
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Archive status',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  Chip(label: Text('Entities: ${data['entity_count'] ?? 0}')),
                  Chip(
                      label: Text(
                          'Containers: ${data['current_fits_container_count'] ?? 0}')),
                  Chip(
                      label: Text(
                          'Indexed objects: ${data['fits_index_entry_count'] ?? 0}')),
                ]),
                const SizedBox(height: 8),
                Expanded(
                  child: SingleChildScrollView(
                    child: Text(
                        'Source: ${config['source_folder'] ?? '-'}\nContainers: ${config['containers_folder'] ?? '-'}\nIndex: ${config['index_path'] ?? '-'}\nExports: ${config['exports_folder'] ?? '-'}'),
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
            if (snapshot.connectionState != ConnectionState.done)
              return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError)
              return Text('Scenarios unavailable: ${snapshot.error}');
            final scenarios =
                (snapshot.data?['scenarios'] as List<dynamic>? ?? <dynamic>[])
                    .cast<Map<String, dynamic>>();
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Scenario library',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Expanded(
                  child: ListView.builder(
                    itemCount: scenarios.length,
                    itemBuilder: (context, index) {
                      final group = scenarios[index];
                      final examples =
                          (group['examples'] as List<dynamic>? ?? <dynamic>[])
                              .cast<dynamic>();
                      return ExpansionTile(
                        dense: true,
                        title: Text('${group['group']}'),
                        children: examples
                            .map((example) => ListTile(
                                dense: true,
                                title: Text('$example'),
                                onTap: () => onSelected('$example')))
                            .toList(),
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
    final structured = result['structured_query'] as Map<String, dynamic>? ??
        <String, dynamic>{};
    final interpretation = result['interpretation'] as Map<String, dynamic>? ??
        <String, dynamic>{};
    final aiSummary = result['ai_summary'] as Map<String, dynamic>?;
    final executionSource = result['execution_source'];
    final executionResult = result['result'] as Map<String, dynamic>?;
    final diagnostics =
        executionResult?['diagnostics'] as Map<String, dynamic>?;
    final rows = (executionResult?['results'] as List<dynamic>? ?? <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: DefaultTabController(
          length: 6,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(spacing: 8, runSpacing: 8, children: [
                if (structured.isNotEmpty)
                  Chip(label: Text('Scope: ${structured['scope'] ?? '-'}')),
                if (structured.isNotEmpty)
                  Chip(
                      label: Text(
                          'Capability: ${structured['capability'] ?? '-'}')),
                if (structured.isNotEmpty)
                  Chip(
                      label: Text(
                          'Execute with: ${structured['execute_with'] ?? '-'}')),
                if (structured['snapshot_id'] != null)
                  Chip(label: Text('Snapshot: ${structured['snapshot_id']}')),
                if (structured['risk_rating'] != null)
                  Chip(label: Text('Risk: ${structured['risk_rating']}')),
                if (structured['jurisdiction'] != null)
                  Chip(
                      label:
                          Text('Jurisdiction: ${structured['jurisdiction']}')),
                if (interpretation.isNotEmpty)
                  Chip(
                      label: Text(
                          'AI used: ${interpretation['ai_used'] ?? false}')),
                if (interpretation['ai_model'] != null)
                  Chip(label: Text('Model: ${interpretation['ai_model']}')),
                if (executionSource != null)
                  Chip(label: Text('Source: $executionSource')),
                if (executionResult != null)
                  Chip(
                      label: Text(
                          'Results: ${executionResult['result_count'] ?? rows.length}')),
                if (aiSummary != null)
                  Chip(
                      label: Text(
                          'AI summary: ${aiSummary['available'] == true ? 'available' : 'not available'}')),
              ]),
              const SizedBox(height: 12),
              const TabBar(
                isScrollable: true,
                tabs: [
                  Tab(icon: Icon(Icons.table_rows_outlined), text: 'Results'),
                  Tab(
                      icon: Icon(Icons.psychology_alt_outlined),
                      text: 'AI summary'),
                  Tab(
                      icon: Icon(Icons.account_tree_outlined),
                      text: 'Structured query'),
                  Tab(
                      icon: Icon(Icons.psychology_alt_outlined),
                      text: 'Interpretation'),
                  Tab(
                      icon: Icon(Icons.troubleshoot_outlined),
                      text: 'Diagnostics'),
                  Tab(icon: Icon(Icons.data_object_outlined), text: 'Raw JSON'),
                ],
              ),
              const SizedBox(height: 12),
              Expanded(
                child: TabBarView(
                  children: [
                    _ResultsTable(rows: rows, result: executionResult),
                    _AiSummaryPanel(summary: aiSummary),
                    _JsonPanel(value: structured.isEmpty ? result : structured),
                    _JsonPanel(
                        value: interpretation.isEmpty
                            ? <String, dynamic>{
                                'message': 'No interpretation block returned.'
                              }
                            : interpretation),
                    _JsonPanel(
                        value: diagnostics ??
                            <String, dynamic>{
                              'message':
                                  'No diagnostics returned for this query.'
                            }),
                    _JsonPanel(value: result),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AiSummaryPanel extends StatelessWidget {
  const _AiSummaryPanel({required this.summary});

  final Map<String, dynamic>? summary;

  @override
  Widget build(BuildContext context) {
    if (summary == null) {
      return const Center(
          child: Text(
              'No AI summary was requested or returned. Enable “Request AI summary” and execute the query.'));
    }
    final available = summary!['available'] == true;
    final text =
        '${summary!['summary'] ?? summary!['warning'] ?? 'No summary text returned.'}';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(spacing: 8, runSpacing: 8, children: [
          Chip(label: Text('Available: $available')),
          if (summary!['provider'] != null)
            Chip(label: Text('Provider: ${summary!['provider']}')),
          if (summary!['model'] != null)
            Chip(label: Text('Model: ${summary!['model']}')),
          if (summary!['evidence_row_count'] != null)
            Chip(
                label:
                    Text('Rows summarised: ${summary!['evidence_row_count']}')),
        ]),
        const SizedBox(height: 12),
        Expanded(
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border.all(
                  color: Theme.of(context).colorScheme.outlineVariant),
              borderRadius: BorderRadius.circular(12),
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: SelectableText(text),
            ),
          ),
        ),
      ],
    );
  }
}

class _ResultsTable extends StatelessWidget {
  const _ResultsTable({required this.rows, required this.result});

  final List<Map<String, dynamic>> rows;
  final Map<String, dynamic>? result;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return _JsonPanel(
          value: result ??
              <String, dynamic>{'message': 'No result rows returned.'});
    }

    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SingleChildScrollView(
          child: DataTable(
            columns: const [
              DataColumn(label: Text('Customer')),
              DataColumn(label: Text('Name')),
              DataColumn(label: Text('Risk')),
              DataColumn(label: Text('Jurisdiction')),
              DataColumn(label: Text('Filename')),
              DataColumn(label: Text('Category')),
              DataColumn(label: Text('Document type')),
              DataColumn(label: Text('Source')),
              DataColumn(label: Text('Retention until')),
              DataColumn(label: Text('Legal hold')),
              DataColumn(label: Text('Cohort source')),
              DataColumn(label: Text('Score')),
              DataColumn(label: Text('Snippet')),
            ],
            rows: rows.map((row) {
              final metadata = row['metadata'] as Map<String, dynamic>? ??
                  <String, dynamic>{};
              final nested = metadata['metadata'] as Map<String, dynamic>? ??
                  <String, dynamic>{};
              String value(String key) =>
                  '${row[key] ?? metadata[key] ?? nested[key] ?? '-'}';
              return DataRow(cells: [
                DataCell(Text(value('entity_external_id'))),
                DataCell(SizedBox(
                    width: 180,
                    child: Text(value('entity_display_name'),
                        overflow: TextOverflow.ellipsis))),
                DataCell(Text(value('risk_rating'))),
                DataCell(Text(value('jurisdiction'))),
                DataCell(SizedBox(
                    width: 260,
                    child: Text(value('filename'),
                        overflow: TextOverflow.ellipsis))),
                DataCell(Text(value('category'))),
                DataCell(Text(value('document_type'))),
                DataCell(Text(value('source_system'))),
                DataCell(Text(value('retention_until'))),
                DataCell(Text(value('legal_hold_status'))),
                DataCell(Text(value('cohort_match_source'))),
                DataCell(Text(value('match_score'))),
                DataCell(SizedBox(
                    width: 480,
                    child: Text(
                        '${row['snippet'] ?? row['text_content'] ?? ''}',
                        overflow: TextOverflow.ellipsis,
                        maxLines: 2))),
              ]);
            }).toList(),
          ),
        ),
      ),
    );
  }
}

class _JsonPanel extends StatelessWidget {
  const _JsonPanel({required this.value});

  final Object value;

  @override
  Widget build(BuildContext context) {
    final encoded = const JsonEncoder.withIndent('  ').convert(value);
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Scrollbar(
        thumbVisibility: true,
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: 1200,
            child: Scrollbar(
              thumbVisibility: true,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: SelectableText(
                  encoded,
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(fontFamily: 'monospace'),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
