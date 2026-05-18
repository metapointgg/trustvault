import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/customer_selector_card.dart';
import '../../shared/selected_customer.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _queryController = TextEditingController(
    text: 'Show me all onboarding documentation for high risk clients in Guernsey.',
  );
  final TextEditingController _entityController = TextEditingController();

  late Future<Map<String, dynamic>> _archiveStatusFuture;
  late Future<Map<String, dynamic>> _scenarioFuture;
  bool _loading = false;
  bool _useSelectedCustomer = false;
  bool _includeAiSummary = true;
  bool _rawDirectFits = false;
  String _interpretationMode = 'auto';
  int _limit = 50;
  Map<String, dynamic>? _result;
  String? _error;

  @override
  void initState() {
    super.initState();
    _archiveStatusFuture = _apiClient.getArchiveStatus();
    _scenarioFuture = _apiClient.getQueryScenarios();
    _syncEntityFromSelectedCustomer();
    SelectedCustomerController.selected.addListener(_syncEntityFromSelectedCustomer);
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_syncEntityFromSelectedCustomer);
    _queryController.dispose();
    _entityController.dispose();
    super.dispose();
  }

  void _syncEntityFromSelectedCustomer() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId != null && externalId.isNotEmpty && _entityController.text != externalId) {
      _entityController.text = externalId;
    }
  }

  Future<void> _run({required bool execute}) async {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;
    final entity = _useSelectedCustomer ? _entityController.text.trim() : null;
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final Map<String, dynamic> result;
      if (!execute) {
        result = await _apiClient.interpretQuery(
          query: query,
          entityExternalId: entity == null || entity.isEmpty ? null : entity,
          mode: _interpretationMode,
        );
      } else if (_rawDirectFits && entity != null && entity.isNotEmpty) {
        result = await _apiClient.searchEntityFits(entity, query);
      } else {
        result = await _apiClient.executeQuery(
          query: query,
          entityExternalId: entity == null || entity.isEmpty ? null : entity,
          mode: _interpretationMode,
          includeAiSummary: _includeAiSummary,
          limit: _limit,
        );
      }
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
      if (example.contains('CUST-000001')) {
        _entityController.text = 'CUST-000001';
      }
    });
  }

  Future<void> _showPreview(Map<String, dynamic> result) async {
    final objectId = '${result['evidence_object_id'] ?? ''}';
    if (objectId.isEmpty || objectId == 'null') return;
    final preview = await _apiClient.getEvidencePreview(objectId);
    if (!mounted) return;

    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
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
        );
      },
    );
  }

  Future<void> _open(String url) async {
    await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
  }

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
                      const Text('Search evidence, interpret natural-language questions, run direct FITS retrievals and inspect the structured query used by TrustVault.'),
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
                  label: const Text('Refresh context'),
                ),
              ],
            ),
            const SizedBox(height: 20),
            LayoutBuilder(
              builder: (context, constraints) {
                final narrow = constraints.maxWidth < 1100;
                final cards = [
                  _ArchiveStatusCard(future: _archiveStatusFuture),
                  _ScenarioPicker(future: _scenarioFuture, onSelected: _setExample),
                ];
                if (narrow) {
                  return Column(children: cards.map((card) => Padding(padding: const EdgeInsets.only(bottom: 16), child: SizedBox(height: 220, child: card))).toList());
                }
                return SizedBox(
                  height: 220,
                  child: Row(
                    children: [
                      Expanded(child: cards[0]),
                      const SizedBox(width: 16),
                      Expanded(child: cards[1]),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(height: 20),
            _QueryBuilderCard(
              queryController: _queryController,
              entityController: _entityController,
              useSelectedCustomer: _useSelectedCustomer,
              includeAiSummary: _includeAiSummary,
              rawDirectFits: _rawDirectFits,
              interpretationMode: _interpretationMode,
              limit: _limit,
              loading: _loading,
              onUseSelectedCustomerChanged: (value) {
                setState(() {
                  _useSelectedCustomer = value;
                  if (value) _syncEntityFromSelectedCustomer();
                });
              },
              onIncludeAiSummaryChanged: (value) => setState(() => _includeAiSummary = value),
              onRawDirectFitsChanged: (value) => setState(() => _rawDirectFits = value),
              onInterpretationModeChanged: (value) => setState(() => _interpretationMode = value),
              onLimitChanged: (value) => setState(() => _limit = value),
              onInterpret: () => _run(execute: false),
              onExecute: () => _run(execute: true),
            ),
            if (_useSelectedCustomer) ...[
              const SizedBox(height: 16),
              CustomerSelectorCard(
                title: 'Selected-customer scope',
                subtitle: 'Used for scoped natural-language search or raw direct FITS search.',
                onChanged: (_) => _syncEntityFromSelectedCustomer(),
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
                      : _UnifiedResultView(result: _result!, onPreview: _showPreview),
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
    required this.rawDirectFits,
    required this.interpretationMode,
    required this.limit,
    required this.loading,
    required this.onUseSelectedCustomerChanged,
    required this.onIncludeAiSummaryChanged,
    required this.onRawDirectFitsChanged,
    required this.onInterpretationModeChanged,
    required this.onLimitChanged,
    required this.onInterpret,
    required this.onExecute,
  });

  final TextEditingController queryController;
  final TextEditingController entityController;
  final bool useSelectedCustomer;
  final bool includeAiSummary;
  final bool rawDirectFits;
  final String interpretationMode;
  final int limit;
  final bool loading;
  final ValueChanged<bool> onUseSelectedCustomerChanged;
  final ValueChanged<bool> onIncludeAiSummaryChanged;
  final ValueChanged<bool> onRawDirectFitsChanged;
  final ValueChanged<String> onInterpretationModeChanged;
  final ValueChanged<int> onLimitChanged;
  final VoidCallback onInterpret;
  final VoidCallback onExecute;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Ask TrustVault', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
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
                    width: narrow ? double.infinity : 260,
                    child: DropdownButtonFormField<String>(
                      value: interpretationMode,
                      decoration: const InputDecoration(labelText: 'Interpretation mode', border: OutlineInputBorder()),
                      items: const [
                        DropdownMenuItem(value: 'auto', child: Text('Auto')),
                        DropdownMenuItem(value: 'deterministic', child: Text('Deterministic')),
                        DropdownMenuItem(value: 'ai', child: Text('AI assisted')),
                      ],
                      onChanged: (value) => onInterpretationModeChanged(value ?? 'auto'),
                    ),
                  ),
                  SizedBox(
                    width: narrow ? double.infinity : 160,
                    child: DropdownButtonFormField<int>(
                      value: limit,
                      decoration: const InputDecoration(labelText: 'Limit', border: OutlineInputBorder()),
                      items: const [25, 50, 100, 250, 500].map((value) => DropdownMenuItem(value: value, child: Text('$value'))).toList(),
                      onChanged: (value) => onLimitChanged(value ?? 50),
                    ),
                  ),
                  SizedBox(
                    width: narrow ? double.infinity : 260,
                    child: TextField(
                      controller: entityController,
                      enabled: useSelectedCustomer,
                      decoration: const InputDecoration(labelText: 'Customer external ID', border: OutlineInputBorder()),
                    ),
                  ),
                ];
                if (narrow) {
                  return Column(children: controls.map((control) => Padding(padding: const EdgeInsets.only(bottom: 12), child: control)).toList());
                }
                return Wrap(spacing: 12, runSpacing: 12, children: controls);
              },
            ),
            const SizedBox(height: 8),
            LayoutBuilder(
              builder: (context, constraints) {
                final narrow = constraints.maxWidth < 980;
                final switches = [
                  _OptionSwitch(title: 'Selected-customer scope', subtitle: 'Scope the query to one customer/FITS archive.', value: useSelectedCustomer, onChanged: onUseSelectedCustomerChanged),
                  _OptionSwitch(title: 'AI summary', subtitle: 'Summarise retrieved evidence rows only.', value: includeAiSummary, onChanged: onIncludeAiSummaryChanged),
                  _OptionSwitch(title: 'Raw direct FITS search', subtitle: 'Bypass natural-language execution for a selected customer.', value: rawDirectFits, onChanged: useSelectedCustomer ? onRawDirectFitsChanged : null),
                ];
                if (narrow) return Column(children: switches);
                return Row(children: switches.map((item) => Expanded(child: item)).toList());
              },
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                FilledButton.icon(onPressed: loading ? null : onExecute, icon: const Icon(Icons.search), label: const Text('Search / Execute')),
                OutlinedButton.icon(onPressed: loading ? null : onInterpret, icon: const Icon(Icons.psychology_alt_outlined), label: const Text('Interpret only')),
                if (loading) const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _OptionSwitch extends StatelessWidget {
  const _OptionSwitch({required this.title, required this.subtitle, required this.value, required this.onChanged});

  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title),
      subtitle: Text(subtitle),
      value: value,
      onChanged: onChanged,
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
                Wrap(spacing: 8, runSpacing: 8, children: [
                  Chip(label: Text('Entities: ${data['entity_count'] ?? 0}')),
                  Chip(label: Text('Containers: ${data['current_fits_container_count'] ?? 0}')),
                  Chip(label: Text('Indexed: ${data['fits_index_entry_count'] ?? 0}')),
                ]),
                const SizedBox(height: 8),
                Expanded(
                  child: SingleChildScrollView(
                    child: Text('Source: ${config['source_folder'] ?? '-'}\nContainers: ${config['containers_folder'] ?? '-'}\nIndex: ${config['index_path'] ?? '-'}\nExports: ${config['exports_folder'] ?? '-'}'),
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
            final scenarios = (snapshot.data?['scenarios'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Example queries', style: Theme.of(context).textTheme.titleLarge),
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
                        children: examples.map((example) => ListTile(dense: true, title: Text('$example'), onTap: () => onSelected('$example'))).toList(),
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

class _UnifiedResultView extends StatelessWidget {
  const _UnifiedResultView({required this.result, required this.onPreview});

  final Map<String, dynamic> result;
  final Future<void> Function(Map<String, dynamic> result) onPreview;

  @override
  Widget build(BuildContext context) {
    final structured = result['structured_query'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final interpretation = result['interpretation'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final aiSummary = result['ai_summary'] as Map<String, dynamic>?;
    final executionResult = result['result'] is Map<String, dynamic> ? result['result'] as Map<String, dynamic> : result;
    final diagnostics = executionResult['diagnostics'] as Map<String, dynamic>?;
    final rows = (executionResult['results'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
    final executionSource = result['execution_source'] ?? executionResult['execution_source'] ?? 'fits_index';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: DefaultTabController(
          length: 6,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(spacing: 8, runSpacing: 8, children: [
                Chip(label: Text('Results: ${executionResult['result_count'] ?? rows.length}')),
                Chip(label: Text('Source: $executionSource')),
                if (structured['snapshot_id'] != null) Chip(label: Text('Snapshot: ${structured['snapshot_id']}')),
                if (structured['risk_rating'] != null) Chip(label: Text('Risk: ${structured['risk_rating']}')),
                if (structured['jurisdiction'] != null) Chip(label: Text('Jurisdiction: ${structured['jurisdiction']}')),
                if (interpretation.isNotEmpty) Chip(label: Text('AI used: ${interpretation['ai_used'] ?? false}')),
                if (interpretation['ai_model'] != null) Chip(label: Text('Model: ${interpretation['ai_model']}')),
                if (aiSummary != null) Chip(label: Text('AI summary: ${aiSummary['available'] == true ? 'available' : 'not available'}')),
              ]),
              const SizedBox(height: 12),
              const TabBar(
                isScrollable: true,
                tabs: [
                  Tab(icon: Icon(Icons.table_rows_outlined), text: 'Results'),
                  Tab(icon: Icon(Icons.psychology_alt_outlined), text: 'AI summary'),
                  Tab(icon: Icon(Icons.account_tree_outlined), text: 'Structured query'),
                  Tab(icon: Icon(Icons.psychology_alt_outlined), text: 'Interpretation'),
                  Tab(icon: Icon(Icons.troubleshoot_outlined), text: 'Diagnostics'),
                  Tab(icon: Icon(Icons.data_object_outlined), text: 'Raw JSON'),
                ],
              ),
              const SizedBox(height: 12),
              Expanded(
                child: TabBarView(
                  children: [
                    _ResultsTable(rows: rows, result: executionResult, onPreview: onPreview),
                    _AiSummaryPanel(summary: aiSummary),
                    _JsonPanel(value: structured.isEmpty ? result : structured),
                    _JsonPanel(value: interpretation.isEmpty ? <String, dynamic>{'message': 'No interpretation block returned.'} : interpretation),
                    _JsonPanel(value: diagnostics ?? <String, dynamic>{'message': 'No diagnostics returned.'}),
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

class _ResultsTable extends StatelessWidget {
  const _ResultsTable({required this.rows, required this.result, required this.onPreview});

  final List<Map<String, dynamic>> rows;
  final Map<String, dynamic> result;
  final Future<void> Function(Map<String, dynamic> result) onPreview;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) return _JsonPanel(value: result);
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
              DataColumn(label: Text('Match')),
              DataColumn(label: Text('Score')),
              DataColumn(label: Text('Snippet')),
              DataColumn(label: Text('Actions')),
            ],
            rows: rows.map((row) {
              final metadata = row['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
              final nested = metadata['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
              String value(String key) => '${row[key] ?? metadata[key] ?? nested[key] ?? '-'}';
              return DataRow(cells: [
                DataCell(Text(value('entity_external_id'))),
                DataCell(SizedBox(width: 180, child: Text(value('entity_display_name'), overflow: TextOverflow.ellipsis))),
                DataCell(Text(value('risk_rating'))),
                DataCell(Text(value('jurisdiction'))),
                DataCell(SizedBox(width: 260, child: Text(value('filename'), overflow: TextOverflow.ellipsis))),
                DataCell(Text(value('category'))),
                DataCell(Text(value('document_type'))),
                DataCell(Text(value('source_system'))),
                DataCell(Text(value('retention_until'))),
                DataCell(Text(value('legal_hold_status'))),
                DataCell(Text(value('cohort_match_source'))),
                DataCell(Text(value('match_score'))),
                DataCell(SizedBox(width: 480, child: Text('${row['snippet'] ?? row['text_content'] ?? ''}', overflow: TextOverflow.ellipsis, maxLines: 2))),
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

class _AiSummaryPanel extends StatelessWidget {
  const _AiSummaryPanel({required this.summary});

  final Map<String, dynamic>? summary;

  @override
  Widget build(BuildContext context) {
    if (summary == null) return const Center(child: Text('No AI summary was requested or returned.'));
    final available = summary!['available'] == true;
    final text = '${summary!['summary'] ?? summary!['warning'] ?? 'No summary text returned.'}';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(spacing: 8, runSpacing: 8, children: [
          Chip(label: Text('Available: $available')),
          if (summary!['provider'] != null) Chip(label: Text('Provider: ${summary!['provider']}')),
          if (summary!['model'] != null) Chip(label: Text('Model: ${summary!['model']}')),
          if (summary!['evidence_row_count'] != null) Chip(label: Text('Rows summarised: ${summary!['evidence_row_count']}')),
        ]),
        const SizedBox(height: 12),
        Expanded(
          child: DecoratedBox(
            decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
            child: SingleChildScrollView(padding: const EdgeInsets.all(16), child: SelectableText(text)),
          ),
        ),
      ],
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
              Text('Search evidence or inspect a query', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              const Text('Use Search / Execute for results, or Interpret only to inspect the structured query before running it.'),
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
