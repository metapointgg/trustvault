import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
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
  final TextEditingController _queryController = TextEditingController(text: 'Show me all onboarding documentation for high risk entities in Guernsey.');
  final TextEditingController _entityController = TextEditingController();
  final TextEditingController _entityFilterController = TextEditingController();

  late Future<Map<String, dynamic>> _scenariosFuture;
  late Future<List<dynamic>> _entitiesFuture;
  bool _selectedEntityOnly = false;
  bool _includeAiSummary = true;
  bool _loading = false;
  String _mode = 'auto';
  int _limit = 50;
  String _entityFilter = '';
  String? _error;
  Map<String, dynamic>? _response;

  @override
  void initState() {
    super.initState();
    _scenariosFuture = _apiClient.getQueryScenarios();
    _entitiesFuture = _apiClient.getCustomers();
    _syncSelectedEntity();
    if (SelectedCustomerController.consumeSearchForSelectedEntityRequest()) {
      _selectedEntityOnly = true;
      _queryController.text = 'Show me onboarding documentation.';
    }
    SelectedCustomerController.selected.addListener(_syncSelectedEntity);
    _entityFilterController.addListener(() => setState(() => _entityFilter = _entityFilterController.text.trim().toLowerCase()));
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_syncSelectedEntity);
    _queryController.dispose();
    _entityController.dispose();
    _entityFilterController.dispose();
    super.dispose();
  }

  void _syncSelectedEntity() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId != null && externalId.isNotEmpty && _entityController.text != externalId) {
      _entityController.text = externalId;
    }
  }

  Future<void> _run() async {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _response = null;
    });
    try {
      final result = await _apiClient.executeQuery(
        query: query,
        entityExternalId: _selectedEntityOnly && _entityController.text.trim().isNotEmpty ? _entityController.text.trim() : null,
        mode: _includeAiSummary && _mode == 'auto' ? 'ai' : _mode,
        includeAiSummary: _includeAiSummary,
        limit: _limit,
      );
      if (!mounted) return;
      setState(() {
        _response = result;
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

  void _applyExample(String example) {
    final cleaned = example
        .replaceAll('customers', 'entities')
        .replaceAll('customer', 'entity')
        .replaceAll('clients', 'entities')
        .replaceAll('client', 'entity')
        .replaceFirst('Use TrustVault to interpret this query but do not execute it: ', '')
        .replaceFirst('Use TrustVault to interpret this query: ', '')
        .replaceFirst('Use TrustVault to execute this query: ', '')
        .replaceFirst('Use TrustVault to execute this query for CUST-000001: ', '')
        .replaceFirst('Use TrustVault to ', '');
    setState(() {
      _queryController.text = cleaned;
      _selectedEntityOnly = cleaned.contains('CUST-000001') || cleaned.toLowerCase().contains('selected entity');
      if (cleaned.contains('CUST-000001')) _entityController.text = 'CUST-000001';
    });
  }

  Future<void> _openRow(Map<String, dynamic> row) async {
    if (row['evidence_object_id'] != null) {
      await _openEvidence(row);
      return;
    }
    final externalId = '${row['entity_external_id'] ?? row['external_id'] ?? ''}'.trim();
    if (externalId.isEmpty || externalId == 'null') return;
    SelectedCustomerController.select(<String, dynamic>{
      'external_id': externalId,
      'display_name': row['entity_display_name'] ?? row['display_name'] ?? externalId,
      'id': row['entity_id'],
      'risk_rating': row['risk_rating'],
      'jurisdiction': row['jurisdiction'],
    });
    if (mounted) context.go('/entities');
  }

  Future<void> _openEvidence(Map<String, dynamic> row) async {
    final objectId = '${row['evidence_object_id'] ?? row['id'] ?? ''}';
    if (objectId.isEmpty || objectId == 'null') return;
    final preview = await _apiClient.getEvidencePreview(objectId);
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${preview['filename'] ?? row['filename'] ?? 'Evidence'}'),
        content: SizedBox(width: 920, height: 700, child: _EvidencePreview(apiClient: _apiClient, preview: preview)),
        actions: [
          TextButton.icon(onPressed: () => launchUrl(Uri.parse(_apiClient.evidenceFileUrl(objectId)), webOnlyWindowName: '_blank'), icon: const Icon(Icons.open_in_new), label: const Text('Open')),
          TextButton.icon(onPressed: () => launchUrl(Uri.parse(_apiClient.evidenceDownloadUrl(objectId)), webOnlyWindowName: '_blank'), icon: const Icon(Icons.download), label: const Text('Download')),
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
        ],
      ),
    );
  }

  void _showJson(String title, Object value) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SizedBox(width: 960, height: 680, child: _JsonPanel(value: value)),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  List<Map<String, dynamic>> _filteredEntities(List<dynamic> rows) {
    final entities = rows.cast<Map<String, dynamic>>();
    if (_entityFilter.isEmpty) return entities.take(12).toList();
    return entities.where((row) => '${row['external_id']} ${row['display_name']} ${row['risk_rating']} ${row['jurisdiction']}'.toLowerCase().contains(_entityFilter)).take(20).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Search & Query', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              const Text('Ask TrustVault a question and review evidence rows. Click evidence rows to preview them, or entity rows to open the entity context.'),
            ])),
            OutlinedButton.icon(
              onPressed: () => setState(() {
                _scenariosFuture = _apiClient.getQueryScenarios();
                _entitiesFuture = _apiClient.getCustomers();
              }),
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh'),
            ),
          ]),
          const SizedBox(height: 20),
          _SearchForm(
            queryController: _queryController,
            entityController: _entityController,
            scenariosFuture: _scenariosFuture,
            selectedEntityOnly: _selectedEntityOnly,
            includeAiSummary: _includeAiSummary,
            mode: _mode,
            limit: _limit,
            loading: _loading,
            onExample: _applyExample,
            onSelectedEntityOnlyChanged: (value) => setState(() {
              _selectedEntityOnly = value;
              if (value) _syncSelectedEntity();
            }),
            onIncludeAiSummaryChanged: (value) => setState(() => _includeAiSummary = value),
            onModeChanged: (value) => setState(() => _mode = value),
            onLimitChanged: (value) => setState(() => _limit = value),
            onSearch: _run,
          ),
          if (_selectedEntityOnly) ...[
            const SizedBox(height: 16),
            _EntityPicker(future: _entitiesFuture, controller: _entityFilterController, rowsBuilder: _filteredEntities, onSelected: (entity) {
              SelectedCustomerController.select(entity);
              _entityController.text = '${entity['external_id']}';
            }),
          ],
          const SizedBox(height: 20),
          if (_error != null) Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)))),
          SizedBox(height: 760, child: _loading ? const Center(child: CircularProgressIndicator()) : _response == null ? const _EmptyState() : _ResultPanel(response: _response!, onOpenRow: _openRow, onPreview: _openEvidence, onJson: _showJson)),
        ]),
      ),
    );
  }
}

class _SearchForm extends StatelessWidget {
  const _SearchForm({required this.queryController, required this.entityController, required this.scenariosFuture, required this.selectedEntityOnly, required this.includeAiSummary, required this.mode, required this.limit, required this.loading, required this.onExample, required this.onSelectedEntityOnlyChanged, required this.onIncludeAiSummaryChanged, required this.onModeChanged, required this.onLimitChanged, required this.onSearch});

  final TextEditingController queryController;
  final TextEditingController entityController;
  final Future<Map<String, dynamic>> scenariosFuture;
  final bool selectedEntityOnly;
  final bool includeAiSummary;
  final String mode;
  final int limit;
  final bool loading;
  final ValueChanged<String> onExample;
  final ValueChanged<bool> onSelectedEntityOnlyChanged;
  final ValueChanged<bool> onIncludeAiSummaryChanged;
  final ValueChanged<String> onModeChanged;
  final ValueChanged<int> onLimitChanged;
  final VoidCallback onSearch;

  @override
  Widget build(BuildContext context) {
    return Card(child: Padding(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [Expanded(child: Text('Ask TrustVault', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700))), _ExamplesButton(future: scenariosFuture, onSelected: onExample)]),
      const SizedBox(height: 12),
      TextField(controller: queryController, minLines: 2, maxLines: 4, decoration: const InputDecoration(labelText: 'Question or search phrase', border: OutlineInputBorder()), onSubmitted: (_) => onSearch()),
      const SizedBox(height: 12),
      Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [
        SizedBox(width: 220, child: DropdownButtonFormField<String>(value: mode, decoration: const InputDecoration(labelText: 'Mode', border: OutlineInputBorder()), items: const [DropdownMenuItem(value: 'auto', child: Text('Auto')), DropdownMenuItem(value: 'deterministic', child: Text('Deterministic')), DropdownMenuItem(value: 'ai', child: Text('AI assisted'))], onChanged: (value) => onModeChanged(value ?? 'auto'))),
        SizedBox(width: 150, child: DropdownButtonFormField<int>(value: limit, decoration: const InputDecoration(labelText: 'Limit', border: OutlineInputBorder()), items: const [25, 50, 100, 250, 500].map((value) => DropdownMenuItem(value: value, child: Text('$value'))).toList(), onChanged: (value) => onLimitChanged(value ?? 50))),
        SizedBox(width: 300, child: SegmentedButton<bool>(segments: const [ButtonSegment(value: false, label: Text('All entities'), icon: Icon(Icons.groups_outlined)), ButtonSegment(value: true, label: Text('Selected entity'), icon: Icon(Icons.person_search_outlined))], selected: <bool>{selectedEntityOnly}, onSelectionChanged: (value) => onSelectedEntityOnlyChanged(value.first))),
        SizedBox(width: 260, child: TextField(controller: entityController, enabled: selectedEntityOnly, decoration: const InputDecoration(labelText: 'Selected entity ID', border: OutlineInputBorder()))),
      ]),
      SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('AI narrative summary'), subtitle: const Text('Use the configured AI provider to explain returned evidence in natural language.'), value: includeAiSummary, onChanged: onIncludeAiSummaryChanged),
      FilledButton.icon(onPressed: loading ? null : onSearch, icon: const Icon(Icons.search), label: const Text('Search')),
    ])));
  }
}

class _ExamplesButton extends StatelessWidget {
  const _ExamplesButton({required this.future, required this.onSelected});
  final Future<Map<String, dynamic>> future;
  final ValueChanged<String> onSelected;
  @override
  Widget build(BuildContext context) => OutlinedButton.icon(icon: const Icon(Icons.lightbulb_outline), label: const Text('Browse examples'), onPressed: () async {
    final data = await future;
    if (!context.mounted) return;
    final selected = await showDialog<String>(context: context, builder: (_) => _ExamplesDialog(data: data));
    if (selected != null) onSelected(selected);
  });
}

class _ExamplesDialog extends StatefulWidget {
  const _ExamplesDialog({required this.data});
  final Map<String, dynamic> data;
  @override
  State<_ExamplesDialog> createState() => _ExamplesDialogState();
}

class _ExamplesDialogState extends State<_ExamplesDialog> {
  final TextEditingController _controller = TextEditingController();
  String _filter = '';
  String _group = 'All';
  @override
  void initState() { super.initState(); _controller.addListener(() => setState(() => _filter = _controller.text.trim().toLowerCase())); }
  @override
  void dispose() { _controller.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    final scenarios = (widget.data['scenarios'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
    final groups = <String>['All', ...scenarios.map((item) => '${item['group']}')];
    final examples = <Map<String, String>>[];
    for (final scenario in scenarios) {
      final group = '${scenario['group']}';
      if (_group != 'All' && _group != group) continue;
      for (final item in (scenario['examples'] as List<dynamic>? ?? <dynamic>[])) {
        final text = '$item'.replaceAll('customers', 'entities').replaceAll('customer', 'entity').replaceAll('clients', 'entities').replaceAll('client', 'entity');
        if (_filter.isEmpty || '$group $text'.toLowerCase().contains(_filter)) examples.add({'group': group, 'text': text});
      }
    }
    return AlertDialog(title: const Text('Example queries'), content: SizedBox(width: 980, height: 680, child: Column(children: [
      Row(children: [Expanded(child: TextField(controller: _controller, decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search examples'))), const SizedBox(width: 12), SizedBox(width: 300, child: DropdownButtonFormField<String>(value: _group, decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Example type'), items: groups.map((group) => DropdownMenuItem(value: group, child: Text(group, overflow: TextOverflow.ellipsis))).toList(), onChanged: (value) => setState(() => _group = value ?? 'All')))]),
      const SizedBox(height: 12),
      Expanded(child: ListView.separated(itemCount: examples.length, separatorBuilder: (_, __) => const Divider(height: 1), itemBuilder: (context, index) { final item = examples[index]; return ListTile(title: Text(item['text']!), subtitle: Text(item['group']!), onTap: () => Navigator.of(context).pop(item['text'])); })),
    ])), actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel'))]);
  }
}

class _EntityPicker extends StatelessWidget {
  const _EntityPicker({required this.future, required this.controller, required this.rowsBuilder, required this.onSelected});
  final Future<List<dynamic>> future;
  final TextEditingController controller;
  final List<Map<String, dynamic>> Function(List<dynamic>) rowsBuilder;
  final ValueChanged<Map<String, dynamic>> onSelected;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text('Find selected entity', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
    const SizedBox(height: 12),
    TextField(controller: controller, decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search by entity name, ID, risk or jurisdiction')),
    const SizedBox(height: 12),
    FutureBuilder<List<dynamic>>(future: future, builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
      if (snapshot.hasError) return Text('Unable to load entities: ${snapshot.error}');
      final rows = rowsBuilder(snapshot.data ?? <dynamic>[]);
      return SizedBox(height: 220, child: ListView.separated(itemCount: rows.length, separatorBuilder: (_, __) => const Divider(height: 1), itemBuilder: (context, index) { final row = rows[index]; return ListTile(dense: true, title: Text('${row['external_id']} · ${row['display_name']}'), subtitle: Text('Risk: ${row['risk_rating'] ?? '-'} · Jurisdiction: ${row['jurisdiction'] ?? '-'}'), trailing: TextButton(onPressed: () => onSelected(row), child: const Text('Use'))); }));
    }),
  ])));
}

class _ResultPanel extends StatelessWidget {
  const _ResultPanel({required this.response, required this.onOpenRow, required this.onPreview, required this.onJson});
  final Map<String, dynamic> response;
  final Future<void> Function(Map<String, dynamic>) onOpenRow;
  final Future<void> Function(Map<String, dynamic>) onPreview;
  final void Function(String, Object) onJson;
  @override
  Widget build(BuildContext context) {
    final result = response['result'] is Map<String, dynamic> ? response['result'] as Map<String, dynamic> : response;
    final rows = (result['results'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
    final summary = '${(response['ai_summary'] as Map<String, dynamic>?)?['summary'] ?? ''}'.replaceAll('customers', 'entities').replaceAll('customer', 'entity');
    return Card(child: Padding(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(spacing: 8, runSpacing: 8, children: [Chip(label: Text('Results: ${result['result_count'] ?? rows.length}')), Chip(label: Text('Source: ${response['execution_source'] ?? '-'}'))]),
      if (summary.trim().isNotEmpty) ...[const SizedBox(height: 12), Container(width: double.infinity, padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12)), child: SelectableText(summary))],
      const SizedBox(height: 12),
      Wrap(spacing: 8, children: [OutlinedButton(onPressed: () => onJson('Structured query', response['structured_query'] ?? {}), child: const Text('Structured query')), OutlinedButton(onPressed: () => onJson('Interpretation', response['interpretation'] ?? {}), child: const Text('Interpretation')), OutlinedButton(onPressed: () => onJson('Diagnostics', result['diagnostics'] ?? {}), child: const Text('Diagnostics')), OutlinedButton(onPressed: () => onJson('Raw JSON', response), child: const Text('Raw JSON'))]),
      const SizedBox(height: 12),
      Expanded(child: rows.isEmpty ? const Center(child: Text('No rows returned.')) : _ResultsTable(rows: rows, onOpenRow: onOpenRow, onPreview: onPreview)),
    ])));
  }
}

class _ResultsTable extends StatelessWidget {
  const _ResultsTable({required this.rows, required this.onOpenRow, required this.onPreview});
  final List<Map<String, dynamic>> rows;
  final Future<void> Function(Map<String, dynamic>) onOpenRow;
  final Future<void> Function(Map<String, dynamic>) onPreview;
  @override
  Widget build(BuildContext context) => SingleChildScrollView(scrollDirection: Axis.horizontal, child: SingleChildScrollView(child: DataTable(showCheckboxColumn: false, columns: const [DataColumn(label: Text('Entity')), DataColumn(label: Text('Name')), DataColumn(label: Text('Risk')), DataColumn(label: Text('Jurisdiction')), DataColumn(label: Text('Filename')), DataColumn(label: Text('Category')), DataColumn(label: Text('Document type')), DataColumn(label: Text('Source')), DataColumn(label: Text('Score')), DataColumn(label: Text('Snippet / Status')), DataColumn(label: Text('Actions'))], rows: rows.map((row) {
    final metadata = row['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final nested = metadata['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    String value(String key) => '${row[key] ?? metadata[key] ?? nested[key] ?? '-'}';
    final snippet = row['snippet'] ?? row['text_content'] ?? row['status'] ?? row['summary_type'] ?? '';
    return DataRow(onSelectChanged: (_) => onOpenRow(row), cells: [DataCell(Text(value('entity_external_id'))), DataCell(SizedBox(width: 180, child: Text(value('entity_display_name'), overflow: TextOverflow.ellipsis))), DataCell(Text(value('risk_rating'))), DataCell(Text(value('jurisdiction'))), DataCell(SizedBox(width: 240, child: Text(value('filename'), overflow: TextOverflow.ellipsis))), DataCell(Text(value('category'))), DataCell(Text(value('document_type'))), DataCell(Text(value('source_system'))), DataCell(Text(value('match_score'))), DataCell(SizedBox(width: 500, child: Text('$snippet', overflow: TextOverflow.ellipsis, maxLines: 2))), DataCell(TextButton.icon(onPressed: row['evidence_object_id'] == null ? () => onOpenRow(row) : () => onPreview(row), icon: Icon(row['evidence_object_id'] == null ? Icons.business_outlined : Icons.visibility_outlined), label: Text(row['evidence_object_id'] == null ? 'Entity' : 'Preview')))]);
  }).toList())));
}

class _EvidencePreview extends StatelessWidget {
  const _EvidencePreview({required this.apiClient, required this.preview});
  final TrustVaultApiClient apiClient;
  final Map<String, dynamic> preview;
  @override
  Widget build(BuildContext context) {
    final kind = '${preview['preview_kind'] ?? 'binary'}';
    final objectId = '${preview['evidence_object_id']}';
    if (kind == 'image') return InteractiveViewer(child: Center(child: Image.network(apiClient.evidenceFileUrl(objectId), fit: BoxFit.contain)));
    if (kind == 'pdf') return const Center(child: Text('PDF preview opens in a new browser tab using Open.'));
    final text = preview['safe_preview'] ?? preview['text_preview'];
    if (kind == 'eml' || kind == 'text') return SingleChildScrollView(child: SelectableText('$text'));
    return Center(child: Text('No inline preview is available for ${preview['content_type'] ?? 'this file type'}'));
  }
}

class _JsonPanel extends StatelessWidget {
  const _JsonPanel({required this.value});
  final Object value;
  @override
  Widget build(BuildContext context) => DecoratedBox(decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)), child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: SizedBox(width: 1400, child: SingleChildScrollView(padding: const EdgeInsets.all(16), child: SelectableText(const JsonEncoder.withIndent('  ').convert(value), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace'))))));
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) => Card(child: Center(child: Padding(padding: const EdgeInsets.all(32), child: Column(mainAxisSize: MainAxisSize.min, children: [Icon(Icons.manage_search_outlined, size: 56, color: Theme.of(context).colorScheme.primary), const SizedBox(height: 12), Text('Search evidence', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)), const SizedBox(height: 8), const Text('Ask a question, select all entities or one entity, then run Search.')]))));
}
