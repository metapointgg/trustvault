import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _queryController = TextEditingController(text: 'Show me all onboarding documentation for high risk clients in Guernsey.');
  final TextEditingController _entityController = TextEditingController();
  final TextEditingController _customerSearchController = TextEditingController();

  late Future<Map<String, dynamic>> _scenarioFuture;
  late Future<List<dynamic>> _customersFuture;
  bool _loading = false;
  bool _useSelectedCustomer = false;
  bool _includeAiSummary = true;
  String _interpretationMode = 'auto';
  int _limit = 50;
  Map<String, dynamic>? _result;
  String? _error;
  String _customerFilter = '';

  @override
  void initState() {
    super.initState();
    _scenarioFuture = _apiClient.getQueryScenarios();
    _customersFuture = _apiClient.getCustomers();
    _syncEntityFromSelectedCustomer();
    SelectedCustomerController.selected.addListener(_syncEntityFromSelectedCustomer);
    _customerSearchController.addListener(() => setState(() => _customerFilter = _customerSearchController.text.trim().toLowerCase()));
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_syncEntityFromSelectedCustomer);
    _queryController.dispose();
    _entityController.dispose();
    _customerSearchController.dispose();
    super.dispose();
  }

  void _syncEntityFromSelectedCustomer() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId != null && externalId.isNotEmpty && _entityController.text != externalId) {
      _entityController.text = externalId;
    }
  }

  Future<void> _run() async {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;
    final entity = _useSelectedCustomer ? _entityController.text.trim() : null;
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final result = await _apiClient.executeQuery(
        query: query,
        entityExternalId: entity == null || entity.isEmpty ? null : entity,
        mode: _interpretationMode,
        includeAiSummary: _includeAiSummary,
        limit: _limit,
      );
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
      if (example.contains('CUST-000001')) _entityController.text = 'CUST-000001';
    });
  }

  Future<void> _showPreview(Map<String, dynamic> result) async {
    final objectId = '${result['evidence_object_id'] ?? ''}';
    if (objectId.isEmpty || objectId == 'null') return;
    final preview = await _apiClient.getEvidencePreview(objectId);
    if (!mounted) return;

    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${preview['filename'] ?? result['filename'] ?? 'Evidence preview'}'),
        content: SizedBox(
          width: 920,
          height: 700,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(label: Text('Kind: ${preview['preview_kind'] ?? '-'}')),
                  Chip(label: Text('Type: ${preview['content_type'] ?? '-'}')),
                  Chip(label: Text('Size: ${preview['size_bytes'] ?? '-'} bytes')),
                  Chip(label: Text('SHA-256: ${preview['sha256'] ?? '-'}')),
                ],
              ),
              const SizedBox(height: 12),
              Expanded(child: _EvidencePreviewBody(apiClient: _apiClient, preview: preview)),
            ],
          ),
        ),
        actions: [
          TextButton.icon(onPressed: () => _open(_apiClient.evidenceFileUrl(objectId)), icon: const Icon(Icons.open_in_new), label: const Text('Open')),
          TextButton.icon(onPressed: () => _open(_apiClient.evidenceDownloadUrl(objectId)), icon: const Icon(Icons.download), label: const Text('Download')),
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
        ],
      ),
    );
  }

  Future<void> _open(String url) async {
    await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
  }

  void _showAnalysis(String title, Object value) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SizedBox(width: 960, height: 680, child: _JsonPanel(value: value)),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  List<Map<String, dynamic>> _filteredCustomers(List<dynamic> customers) {
    final rows = customers.cast<Map<String, dynamic>>();
    if (_customerFilter.isEmpty) return rows.take(12).toList();
    return rows.where((row) {
      final haystack = '${row['external_id']} ${row['display_name']} ${row['risk_rating']} ${row['jurisdiction']}'.toLowerCase();
      return haystack.contains(_filter);
    }).take(20).toList();
  }

  String get _filter => _customerFilter;

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
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
                      Text('Search & Query', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      const Text('Ask TrustVault a question and review the returned evidence rows. Analysis details are available separately from the results grid.'),
                    ],
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: () => setState(() {
                    _scenarioFuture = _apiClient.getQueryScenarios();
                    _customersFuture = _apiClient.getCustomers();
                  }),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh'),
                ),
              ],
            ),
            const SizedBox(height: 20),
            _QueryBuilderCard(
              queryController: _queryController,
              entityController: _entityController,
              useSelectedCustomer: _useSelectedCustomer,
              includeAiSummary: _includeAiSummary,
              interpretationMode: _interpretationMode,
              limit: _limit,
              loading: _loading,
              scenarioFuture: _scenarioFuture,
              onScenarioSelected: _setExample,
              onUseSelectedCustomerChanged: (value) {
                setState(() {
                  _useSelectedCustomer = value;
                  if (value) _syncEntityFromSelectedCustomer();
                });
              },
              onIncludeAiSummaryChanged: (value) => setState(() => _includeAiSummary = value),
              onInterpretationModeChanged: (value) => setState(() => _interpretationMode = value),
              onLimitChanged: (value) => setState(() => _limit = value),
              onExecute: _run,
            ),
            if (_useSelectedCustomer) ...[
              const SizedBox(height: 16),
              _SelectedCustomerSearch(
                future: _customersFuture,
                filterController: _customerSearchController,
                customers: _filteredCustomers,
                onSelected: (customer) {
                  SelectedCustomerController.select(customer);
                  _entityController.text = '${customer['external_id']}';
                },
              ),
            ],
            const SizedBox(height: 20),
            if (_error != null)
              Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)))),
            SizedBox(
              height: 760,
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _result == null
                      ? const _EmptySearchState()
                      : _UnifiedResultView(result: _result!, onPreview: _showPreview, onShowAnalysis: _showAnalysis),
            ),
          ],
        ),
      ),
    );
  }
}

class _QueryBuilderCard extends StatelessWidget {
  const _QueryBuilderCard({
    required this.queryController,
    required this.entityController,
    required this.useSelectedCustomer,
    required this.includeAiSummary,
    required this.interpretationMode,
    required this.limit,
    required this.loading,
    required this.scenarioFuture,
    required this.onScenarioSelected,
    required this.onUseSelectedCustomerChanged,
    required this.onIncludeAiSummaryChanged,
    required this.onInterpretationModeChanged,
    required this.onLimitChanged,
    required this.onExecute,
  });

  final TextEditingController queryController;
  final TextEditingController entityController;
  final bool useSelectedCustomer;
  final bool includeAiSummary;
  final String interpretationMode;
  final int limit;
  final bool loading;
  final Future<Map<String, dynamic>> scenarioFuture;
  final ValueChanged<String> onScenarioSelected;
  final ValueChanged<bool> onUseSelectedCustomerChanged;
  final ValueChanged<bool> onIncludeAiSummaryChanged;
  final ValueChanged<String> onInterpretationModeChanged;
  final ValueChanged<int> onLimitChanged;
  final VoidCallback onExecute;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text('Ask TrustVault', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700))),
                _ExampleMenu(future: scenarioFuture, onSelected: onScenarioSelected),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: queryController,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Question or search phrase',
                hintText: 'Example: Show me all onboarding documentation for high risk clients in Guernsey',
                border: OutlineInputBorder(),
              ),
              onSubmitted: (_) => onExecute(),
            ),
            const SizedBox(height: 12),
            LayoutBuilder(
              builder: (context, constraints) {
                final narrow = constraints.maxWidth < 980;
                final controls = [
                  SizedBox(
                    width: narrow ? double.infinity : 220,
                    child: DropdownButtonFormField<String>(
                      value: interpretationMode,
                      decoration: const InputDecoration(labelText: 'Mode', border: OutlineInputBorder()),
                      items: const [
                        DropdownMenuItem(value: 'auto', child: Text('Auto')),
                        DropdownMenuItem(value: 'deterministic', child: Text('Deterministic')),
                        DropdownMenuItem(value: 'ai', child: Text('AI assisted')),
                      ],
                      onChanged: (value) => onInterpretationModeChanged(value ?? 'auto'),
                    ),
                  ),
                  SizedBox(
                    width: narrow ? double.infinity : 150,
                    child: DropdownButtonFormField<int>(
                      value: limit,
                      decoration: const InputDecoration(labelText: 'Limit', border: OutlineInputBorder()),
                      items: const [25, 50, 100, 250, 500].map((value) => DropdownMenuItem(value: value, child: Text('$value'))).toList(),
                      onChanged: (value) => onLimitChanged(value ?? 50),
                    ),
                  ),
                  SizedBox(
                    width: narrow ? double.infinity : 280,
                    child: SegmentedButton<bool>(
                      segments: const [
                        ButtonSegment<bool>(value: false, label: Text('All customers'), icon: Icon(Icons.groups_outlined)),
                        ButtonSegment<bool>(value: true, label: Text('Selected customer'), icon: Icon(Icons.person_search_outlined)),
                      ],
                      selected: <bool>{useSelectedCustomer},
                      onSelectionChanged: (value) => onUseSelectedCustomerChanged(value.first),
                    ),
                  ),
                  SizedBox(
                    width: narrow ? double.infinity : 260,
                    child: TextField(
                      controller: entityController,
                      enabled: useSelectedCustomer,
                      decoration: const InputDecoration(labelText: 'Selected customer ID', border: OutlineInputBorder()),
                    ),
                  ),
                ];
                if (narrow) return Column(children: controls.map((control) => Padding(padding: const EdgeInsets.only(bottom: 12), child: control)).toList());
                return Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: controls);
              },
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Narrative summary'),
              subtitle: const Text('Show a plain-English summary above the results grid. Auto mode uses TrustVault deterministic summaries; AI assisted mode can use LM Studio.'),
              value: includeAiSummary,
              onChanged: onIncludeAiSummaryChanged,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                FilledButton.icon(onPressed: loading ? null : onExecute, icon: const Icon(Icons.search), label: const Text('Search')),
                if (loading) const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ExampleMenu extends StatelessWidget {
  const _ExampleMenu({required this.future, required this.onSelected});

  final Future<Map<String, dynamic>> future;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done || snapshot.hasError) {
          return OutlinedButton.icon(onPressed: null, icon: const Icon(Icons.lightbulb_outline), label: const Text('Examples'));
        }
        final scenarios = (snapshot.data?['scenarios'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
        final examples = <String>[];
        for (final scenario in scenarios) {
          examples.addAll((scenario['examples'] as List<dynamic>? ?? <dynamic>[]).map((item) => '$item'));
        }
        return PopupMenuButton<String>(
          tooltip: 'Example queries',
          onSelected: onSelected,
          itemBuilder: (context) => examples.take(24).map((example) => PopupMenuItem<String>(value: example, child: SizedBox(width: 620, child: Text(example)))).toList(),
          child: OutlinedButton.icon(onPressed: null, icon: const Icon(Icons.lightbulb_outline), label: const Text('Examples')),
        );
      },
    );
  }
}

class _SelectedCustomerSearch extends StatelessWidget {
  const _SelectedCustomerSearch({required this.future, required this.filterController, required this.customers, required this.onSelected});

  final Future<List<dynamic>> future;
  final TextEditingController filterController;
  final List<Map<String, dynamic>> Function(List<dynamic> customers) customers;
  final ValueChanged<Map<String, dynamic>> onSelected;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Find selected customer', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            TextField(
              controller: filterController,
              decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search by customer name, ID, risk or jurisdiction'),
            ),
            const SizedBox(height: 12),
            FutureBuilder<List<dynamic>>(
              future: future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
                if (snapshot.hasError) return Text('Unable to load customers: ${snapshot.error}');
                final rows = customers(snapshot.data ?? <dynamic>[]);
                return SizedBox(
                  height: 220,
                  child: rows.isEmpty
                      ? const Center(child: Text('No matching customers.'))
                      : ListView.separated(
                          itemCount: rows.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final row = rows[index];
                            return ListTile(
                              dense: true,
                              title: Text('${row['external_id']} · ${row['display_name']}'),
                              subtitle: Text('Risk: ${row['risk_rating'] ?? '-'} · Jurisdiction: ${row['jurisdiction'] ?? '-'}'),
                              trailing: TextButton(onPressed: () => onSelected(row), child: const Text('Use')),
                            );
                          },
                        ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _UnifiedResultView extends StatelessWidget {
  const _UnifiedResultView({required this.result, required this.onPreview, required this.onShowAnalysis});

  final Map<String, dynamic> result;
  final Future<void> Function(Map<String, dynamic> result) onPreview;
  final void Function(String title, Object value) onShowAnalysis;

  @override
  Widget build(BuildContext context) {
    final structured = result['structured_query'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final interpretation = result['interpretation'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final aiSummary = result['ai_summary'] as Map<String, dynamic>?;
    final executionResult = result['result'] is Map<String, dynamic> ? result['result'] as Map<String, dynamic> : result;
    final diagnostics = executionResult['diagnostics'] as Map<String, dynamic>?;
    final rows = (executionResult['results'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
    final executionSource = result['execution_source'] ?? executionResult['execution_source'] ?? 'fits_index';
    final summaryText = _searchSummaryText(aiSummary: aiSummary, rows: rows, executionResult: executionResult, executionSource: '$executionSource');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(spacing: 8, runSpacing: 8, children: [
              Chip(label: Text('Results: ${executionResult['result_count'] ?? rows.length}')),
              Chip(label: Text('Source: $executionSource')),
              if (structured['snapshot_id'] != null) Chip(label: Text('Snapshot: ${structured['snapshot_id']}')),
              if (structured['risk_rating'] != null) Chip(label: Text('Risk: ${structured['risk_rating']}')),
              if (structured['jurisdiction'] != null) Chip(label: Text('Jurisdiction: ${structured['jurisdiction']}')),
              Chip(label: Text('AI used: ${interpretation['ai_used'] ?? false}')),
            ]),
            if (summaryText != null && summaryText.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                ),
                child: SelectableText(summaryText),
              ),
            ],
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton.icon(onPressed: () => onShowAnalysis('Structured query', structured), icon: const Icon(Icons.account_tree_outlined), label: const Text('Structured query')),
                OutlinedButton.icon(onPressed: () => onShowAnalysis('Interpretation', interpretation), icon: const Icon(Icons.psychology_alt_outlined), label: const Text('Interpretation')),
                OutlinedButton.icon(onPressed: () => onShowAnalysis('Diagnostics', diagnostics ?? <String, dynamic>{}), icon: const Icon(Icons.troubleshoot_outlined), label: const Text('Diagnostics')),
                OutlinedButton.icon(onPressed: () => onShowAnalysis('Raw JSON', result), icon: const Icon(Icons.data_object_outlined), label: const Text('Raw JSON')),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(child: _ResultsTable(rows: rows, result: executionResult, onPreview: onPreview)),
          ],
        ),
      ),
    );
  }
}

String? _searchSummaryText({required Map<String, dynamic>? aiSummary, required List<Map<String, dynamic>> rows, required Map<String, dynamic> executionResult, required String executionSource}) {
  if (aiSummary == null) return null;
  final raw = '${aiSummary['summary'] ?? aiSummary['warning'] ?? ''}'.trim();
  if (raw.isEmpty) return null;
  if (_looksLikeRowDump(raw)) return _conciseEvidenceSummary(rows: rows, executionResult: executionResult, executionSource: executionSource);
  return raw;
}

bool _looksLikeRowDump(String value) {
  final lower = value.toLowerCase();
  return lower.startsWith('fits_index:') || lower.startsWith('direct_fits_container:') || lower.contains('; sha256=') || lower.contains('entity_external_id=');
}

String _conciseEvidenceSummary({required List<Map<String, dynamic>> rows, required Map<String, dynamic> executionResult, required String executionSource}) {
  final total = executionResult['result_count'] ?? rows.length;
  final entities = <String>{};
  final categories = <String, int>{};
  final documentTypes = <String, int>{};
  final examples = <String>[];

  for (final row in rows) {
    final metadata = row['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final nested = metadata['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final entity = '${row['entity_external_id'] ?? metadata['entity_external_id'] ?? nested['entity_external_id'] ?? ''}'.trim();
    final category = '${row['category'] ?? metadata['category'] ?? nested['category'] ?? ''}'.trim();
    final documentType = '${row['document_type'] ?? metadata['document_type'] ?? nested['document_type'] ?? row['object_type'] ?? ''}'.trim();
    final filename = '${row['filename'] ?? metadata['filename'] ?? nested['filename'] ?? ''}'.trim();
    if (entity.isNotEmpty) entities.add(entity);
    if (category.isNotEmpty) categories[category] = (categories[category] ?? 0) + 1;
    if (documentType.isNotEmpty) documentTypes[documentType] = (documentTypes[documentType] ?? 0) + 1;
    if (filename.isNotEmpty && examples.length < 5) examples.add(filename);
  }

  final lines = <String>[
    'TrustVault found $total evidence row${total == 1 ? '' : 's'} from $executionSource across ${entities.length} customer${entities.length == 1 ? '' : 's'}.',
  ];
  if (entities.isNotEmpty) lines.add('Customers: ${entities.take(8).join(', ')}${entities.length > 8 ? '…' : ''}.');
  if (categories.isNotEmpty) lines.add('Categories: ${_countsText(categories)}.');
  if (documentTypes.isNotEmpty) lines.add('Document types: ${_countsText(documentTypes)}.');
  if (examples.isNotEmpty) lines.add('Example files: ${examples.join(', ')}${rows.length > examples.length ? '…' : ''}.');
  lines.add('Use the results grid for the full evidence list, previews and SHA-256 details. The preserved FITS evidence and payload hashes remain the source of truth.');
  return lines.join('\n');
}

String _countsText(Map<String, int> counts) {
  final sorted = counts.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
  return sorted.take(6).map((entry) => '${entry.key} (${entry.value})').join(', ');
}

class _ResultsTable extends StatelessWidget {
  const _ResultsTable({required this.rows, required this.result, required this.onPreview});

  final List<Map<String, dynamic>> rows;
  final Map<String, dynamic> result;
  final Future<void> Function(Map<String, dynamic> result) onPreview;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return Center(
        child: Text('No rows returned. Result count: ${result['result_count'] ?? 0}'),
      );
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
              DataColumn(label: Text('Score')),
              DataColumn(label: Text('Snippet / Status')),
              DataColumn(label: Text('Actions')),
            ],
            rows: rows.map((row) {
              final metadata = row['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
              final nested = metadata['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
              String value(String key) => '${row[key] ?? metadata[key] ?? nested[key] ?? '-'}';
              final snippet = row['snippet'] ?? row['text_content'] ?? row['status'] ?? row['summary_type'] ?? '';
              return DataRow(cells: [
                DataCell(Text(value('entity_external_id'))),
                DataCell(SizedBox(width: 180, child: Text(value('entity_display_name'), overflow: TextOverflow.ellipsis))),
                DataCell(Text(value('risk_rating'))),
                DataCell(Text(value('jurisdiction'))),
                DataCell(SizedBox(width: 240, child: Text(value('filename'), overflow: TextOverflow.ellipsis))),
                DataCell(Text(value('category'))),
                DataCell(Text(value('document_type'))),
                DataCell(Text(value('source_system'))),
                DataCell(Text(value('retention_until'))),
                DataCell(Text(value('legal_hold_status'))),
                DataCell(Text(value('match_score'))),
                DataCell(SizedBox(width: 500, child: Text('$snippet', overflow: TextOverflow.ellipsis, maxLines: 2))),
                DataCell(TextButton.icon(
                  onPressed: row['evidence_object_id'] == null ? null : () => onPreview(row),
                  icon: const Icon(Icons.visibility_outlined),
                  label: const Text('Preview'),
                )),
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
      decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
      child: Scrollbar(
        thumbVisibility: true,
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: 1400,
            child: Scrollbar(
              thumbVisibility: true,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: SelectableText(encoded, style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptySearchState extends StatelessWidget {
  const _EmptySearchState();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.manage_search_outlined, size: 56, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 12),
              Text('Search evidence', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              const Text('Ask a question, select all customers or one customer, then run Search.'),
            ],
          ),
        ),
      ),
    );
  }
}

class _EvidencePreviewBody extends StatelessWidget {
  const _EvidencePreviewBody({required this.apiClient, required this.preview});

  final TrustVaultApiClient apiClient;
  final Map<String, dynamic> preview;

  @override
  Widget build(BuildContext context) {
    final kind = '${preview['preview_kind'] ?? 'binary'}';
    final objectId = '${preview['evidence_object_id']}';
    if (kind == 'image') return InteractiveViewer(child: Center(child: Image.network(apiClient.evidenceFileUrl(objectId), fit: BoxFit.contain)));
    if (kind == 'pdf') {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.picture_as_pdf_outlined, size: 64),
            const SizedBox(height: 12),
            const Text('PDF preview opens in a new browser tab.'),
            const SizedBox(height: 12),
            FilledButton.icon(onPressed: () => launchUrl(Uri.parse(apiClient.evidenceFileUrl(objectId)), webOnlyWindowName: '_blank'), icon: const Icon(Icons.open_in_new), label: const Text('Open PDF')),
          ],
        ),
      );
    }
    final text = preview['safe_preview'] ?? preview['text_preview'];
    if (kind == 'eml' || kind == 'text') return SingleChildScrollView(child: SelectableText('$text'));
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.insert_drive_file_outlined, size: 64),
          const SizedBox(height: 12),
          Text('No inline preview is available for ${preview['content_type'] ?? 'this file type'}.'),
        ],
      ),
    );
  }
}
