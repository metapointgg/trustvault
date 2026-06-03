import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../core/auth/auth_controller.dart';
import '../../shared/evidence_pdf_viewer.dart';
import '../../shared/selected_customer.dart';
import '../../shared/trustvault_data_grid.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final _queryApi = _SearchQueryApi();
  final TextEditingController _queryController = TextEditingController(text: 'Show me high risk entities in Guernsey who are missing onboarding documentation');
  final TextEditingController _entityController = TextEditingController();
  final TextEditingController _entityFilterController = TextEditingController();

  late Future<Map<String, dynamic>> _scenariosFuture;
  late Future<Map<String, dynamic>> _industryPacksFuture;
  late Future<List<dynamic>> _entitiesFuture;
  bool _selectedEntityOnly = false;
  bool _includeAiSummary = true;
  bool _loading = false;
  String _mode = 'auto';
  String _searchIndustry = 'auto';
  int _limit = 50;
  String _entityFilter = '';
  String? _error;
  Map<String, dynamic>? _response;

  @override
  void initState() {
    super.initState();
    _reloadLookups();
    _syncSelectedEntity();
    if (SelectedCustomerController.consumeSearchForSelectedEntityRequest()) {
      _selectedEntityOnly = true;
      _queryController.text = 'Show me onboarding documentation.';
    }
    SelectedCustomerController.selected.addListener(_syncSelectedEntity);
    _entityFilterController.addListener(() => setState(() => _entityFilter = _entityFilterController.text.trim().toLowerCase()));
  }

  void _reloadLookups() {
    _scenariosFuture = _apiClient.getQueryScenarios();
    _industryPacksFuture = _queryApi.getIndustryPacks();
    _entitiesFuture = _apiClient.getCustomers();
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
      final result = await _queryApi.executeQuery(
        query: query,
        entityExternalId: _selectedEntityOnly && _entityController.text.trim().isNotEmpty ? _entityController.text.trim() : null,
        industryKey: _searchIndustry == 'auto' ? null : _searchIndustry,
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
      _searchIndustry = _inferIndustryFromText(cleaned);
      _selectedEntityOnly = cleaned.contains('CUST-000001') || cleaned.toLowerCase().contains('selected entity');
      if (cleaned.contains('CUST-000001')) _entityController.text = 'CUST-000001';
    });
  }

  String _inferIndustryFromText(String value) {
    final lower = value.toLowerCase();
    if (lower.contains('supplier') || lower.contains('vendor') || lower.contains('iso 27001') || lower.contains('soc 2')) return 'supplier_due_diligence';
    if (lower.contains('patient') || lower.contains('oncology') || lower.contains('dr jones') || lower.contains('cancer') || lower.contains('consent')) return 'healthcare';
    if (lower.contains('entity') || lower.contains('cdd') || lower.contains('source of funds') || lower.contains('screening') || lower.contains('onboarding')) return 'financial_services';
    return 'auto';
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
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Search & Query', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                const Text('Ask TrustVault a question, choose the industry context for this search, and review matching entities or evidence.'),
              ]),
            ),
            OutlinedButton.icon(
              onPressed: () => setState(_reloadLookups),
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh'),
            ),
          ]),
          const SizedBox(height: 20),
          _SearchForm(
            queryController: _queryController,
            entityController: _entityController,
            scenariosFuture: _scenariosFuture,
            industryPacksFuture: _industryPacksFuture,
            searchIndustry: _searchIndustry,
            selectedEntityOnly: _selectedEntityOnly,
            includeAiSummary: _includeAiSummary,
            mode: _mode,
            limit: _limit,
            loading: _loading,
            onExample: _applyExample,
            onSearchIndustryChanged: (value) => setState(() => _searchIndustry = value),
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
            _EntityPicker(
              future: _entitiesFuture,
              controller: _entityFilterController,
              rowsBuilder: _filteredEntities,
              onSelected: (entity) {
                SelectedCustomerController.select(entity);
                _entityController.text = '${entity['external_id']}';
              },
            ),
          ],
          const SizedBox(height: 20),
          if (_error != null) Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)))),
          if (_loading)
            const SizedBox(height: 420, child: Center(child: CircularProgressIndicator()))
          else if (_response == null)
            const _EmptyState()
          else
            _ResultPanel(response: _response!, onOpenRow: _openRow, onPreview: _openEvidence, onJson: _showJson),
          const SizedBox(height: 32),
        ]),
      ),
    );
  }
}

class _SearchForm extends StatelessWidget {
  const _SearchForm({
    required this.queryController,
    required this.entityController,
    required this.scenariosFuture,
    required this.industryPacksFuture,
    required this.searchIndustry,
    required this.selectedEntityOnly,
    required this.includeAiSummary,
    required this.mode,
    required this.limit,
    required this.loading,
    required this.onExample,
    required this.onSearchIndustryChanged,
    required this.onSelectedEntityOnlyChanged,
    required this.onIncludeAiSummaryChanged,
    required this.onModeChanged,
    required this.onLimitChanged,
    required this.onSearch,
  });

  final TextEditingController queryController;
  final TextEditingController entityController;
  final Future<Map<String, dynamic>> scenariosFuture;
  final Future<Map<String, dynamic>> industryPacksFuture;
  final String searchIndustry;
  final bool selectedEntityOnly;
  final bool includeAiSummary;
  final String mode;
  final int limit;
  final bool loading;
  final ValueChanged<String> onExample;
  final ValueChanged<String> onSearchIndustryChanged;
  final ValueChanged<bool> onSelectedEntityOnlyChanged;
  final ValueChanged<bool> onIncludeAiSummaryChanged;
  final ValueChanged<String> onModeChanged;
  final ValueChanged<int> onLimitChanged;
  final VoidCallback onSearch;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text('Ask TrustVault', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700))),
            _ExamplesButton(future: scenariosFuture, onSelected: onExample),
          ]),
          const SizedBox(height: 12),
          TextField(
            controller: queryController,
            minLines: 2,
            maxLines: 4,
            decoration: const InputDecoration(labelText: 'Question or search phrase', border: OutlineInputBorder()),
            onSubmitted: (_) => onSearch(),
          ),
          const SizedBox(height: 12),
          Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [
            SizedBox(
              width: 330,
              child: FutureBuilder<Map<String, dynamic>>(
                future: industryPacksFuture,
                builder: (context, snapshot) {
                  final packs = (snapshot.data?['industry_packs'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
                  final values = <String>{'auto', ...packs.map((pack) => '${pack['key']}')};
                  final selected = values.contains(searchIndustry) ? searchIndustry : 'auto';
                  return DropdownButtonFormField<String>(
                    value: selected,
                    decoration: const InputDecoration(labelText: 'Search context', helperText: 'Industry vocabulary for this query', border: OutlineInputBorder()),
                    items: <DropdownMenuItem<String>>[
                      const DropdownMenuItem(value: 'auto', child: Text('Auto / infer from query')),
                      ...packs.map((pack) => DropdownMenuItem(value: '${pack['key']}', child: Text('${pack['label']}'))),
                    ],
                    onChanged: loading ? null : (value) => onSearchIndustryChanged(value ?? 'auto'),
                  );
                },
              ),
            ),
            SizedBox(
              width: 220,
              child: DropdownButtonFormField<String>(
                value: mode,
                decoration: const InputDecoration(labelText: 'Mode', border: OutlineInputBorder()),
                items: const [
                  DropdownMenuItem(value: 'auto', child: Text('Auto')),
                  DropdownMenuItem(value: 'deterministic', child: Text('Deterministic')),
                  DropdownMenuItem(value: 'ai', child: Text('AI assisted')),
                ],
                onChanged: loading ? null : (value) => onModeChanged(value ?? 'auto'),
              ),
            ),
            SizedBox(
              width: 150,
              child: DropdownButtonFormField<int>(
                value: limit,
                decoration: const InputDecoration(labelText: 'Limit', border: OutlineInputBorder()),
                items: const [25, 50, 100, 250, 500].map((value) => DropdownMenuItem(value: value, child: Text('$value'))).toList(),
                onChanged: loading ? null : (value) => onLimitChanged(value ?? 50),
              ),
            ),
            SizedBox(
              width: 300,
              child: SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: false, label: Text('All entities'), icon: Icon(Icons.groups_outlined)),
                  ButtonSegment(value: true, label: Text('Selected entity'), icon: Icon(Icons.person_search_outlined)),
                ],
                selected: <bool>{selectedEntityOnly},
                onSelectionChanged: loading ? null : (value) => onSelectedEntityOnlyChanged(value.first),
              ),
            ),
            SizedBox(
              width: 260,
              child: TextField(controller: entityController, enabled: selectedEntityOnly && !loading, decoration: const InputDecoration(labelText: 'Selected entity ID', border: OutlineInputBorder())),
            ),
          ]),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('AI narrative summary'),
            subtitle: const Text('Shows a short narrative above the grid. The evidence grid remains the primary result.'),
            value: includeAiSummary,
            onChanged: loading ? null : onIncludeAiSummaryChanged,
          ),
          FilledButton.icon(onPressed: loading ? null : onSearch, icon: const Icon(Icons.search), label: const Text('Search')),
        ]),
      ),
    );
  }
}

class _SearchQueryApi {
  _SearchQueryApi()
      : _dio = Dio(BaseOptions(
          baseUrl: const String.fromEnvironment('TRUSTVAULT_API_BASE_URL', defaultValue: 'http://localhost:8000'),
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 60),
        )) {
    _dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      final token = AuthController.instance.accessToken;
      if (token != null && token.isNotEmpty) options.headers['Authorization'] = 'Bearer $token';
      handler.next(options);
    }));
  }

  final Dio _dio;

  Future<Map<String, dynamic>> getIndustryPacks() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/settings/industry-packs');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> executeQuery({required String query, String? entityExternalId, String? industryKey, int limit = 50, String mode = 'auto', bool includeAiSummary = false}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/query/execute', data: <String, dynamic>{
      'query': query,
      'limit': limit,
      'mode': mode,
      'include_ai_summary': includeAiSummary,
      if (entityExternalId != null && entityExternalId.isNotEmpty) 'entity_external_id': entityExternalId,
      if (industryKey != null && industryKey.isNotEmpty && industryKey != 'auto') 'industry_key': industryKey,
    });
    return response.data ?? <String, dynamic>{};
  }
}

class _ExamplesButton extends StatelessWidget {
  const _ExamplesButton({required this.future, required this.onSelected});
  final Future<Map<String, dynamic>> future;
  final ValueChanged<String> onSelected;
  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
      icon: const Icon(Icons.lightbulb_outline),
      label: const Text('Browse examples'),
      onPressed: () async {
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
  void initState() {
    super.initState();
    _controller.addListener(() => setState(() => _filter = _controller.text.trim().toLowerCase()));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

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
    return AlertDialog(
      title: const Text('Example queries'),
      content: SizedBox(
        width: 980,
        height: 680,
        child: Column(children: [
          Row(children: [
            Expanded(child: TextField(controller: _controller, decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search examples'))),
            const SizedBox(width: 12),
            SizedBox(
              width: 300,
              child: DropdownButtonFormField<String>(
                value: _group,
                decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Example type'),
                items: groups.map((group) => DropdownMenuItem(value: group, child: Text(group, overflow: TextOverflow.ellipsis))).toList(),
                onChanged: (value) => setState(() => _group = value ?? 'All'),
              ),
            ),
          ]),
          const SizedBox(height: 12),
          Expanded(
            child: ListView.separated(
              itemCount: examples.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = examples[index];
                return ListTile(title: Text(item['text']!), subtitle: Text(item['group']!), onTap: () => Navigator.of(context).pop(item['text']));
              },
            ),
          ),
        ]),
      ),
      actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel'))],
    );
  }
}

class _EntityPicker extends StatelessWidget {
  const _EntityPicker({required this.future, required this.controller, required this.rowsBuilder, required this.onSelected});
  final Future<List<dynamic>> future;
  final TextEditingController controller;
  final List<Map<String, dynamic>> Function(List<dynamic>) rowsBuilder;
  final ValueChanged<Map<String, dynamic>> onSelected;
  @override
  Widget build(BuildContext context) => Card(
      child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Find selected entity', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            TextField(controller: controller, decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search by entity name, ID, risk or jurisdiction')),
            const SizedBox(height: 12),
            FutureBuilder<List<dynamic>>(
                future: future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
                  if (snapshot.hasError) return Text('Unable to load entities: ${snapshot.error}');
                  final rows = rowsBuilder(snapshot.data ?? <dynamic>[]);
                  return SizedBox(
                      height: 220,
                      child: ListView.separated(
                          itemCount: rows.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final row = rows[index];
                            return ListTile(
                                dense: true,
                                title: Text('${row['external_id']} · ${row['display_name']}'),
                                subtitle: Text('Risk: ${row['risk_rating'] ?? '-'} · Jurisdiction: ${row['jurisdiction'] ?? '-'}'),
                                trailing: TextButton(onPressed: () => onSelected(row), child: const Text('Use')));
                          }));
                }),
          ])));
}

class _ResultPanel extends StatefulWidget {
  const _ResultPanel({required this.response, required this.onOpenRow, required this.onPreview, required this.onJson});
  final Map<String, dynamic> response;
  final Future<void> Function(Map<String, dynamic>) onOpenRow;
  final Future<void> Function(Map<String, dynamic>) onPreview;
  final void Function(String, Object) onJson;

  @override
  State<_ResultPanel> createState() => _ResultPanelState();
}

class _ResultPanelState extends State<_ResultPanel> {
  bool _summaryExpanded = false;

  @override
  Widget build(BuildContext context) {
    final result = widget.response['result'] is Map<String, dynamic> ? widget.response['result'] as Map<String, dynamic> : widget.response;
    final rows = (result['results'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().map(_flattenRow).toList();
    final rawSummary = '${(widget.response['ai_summary'] as Map<String, dynamic>?)?['summary'] ?? ''}';
    final summary = _normaliseSummary(rawSummary);
    final contextKey = ((widget.response['interpretation'] as Map<String, dynamic>?)?['active_industry_context'] as Map<String, dynamic>?)?['industry_key'];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(spacing: 8, runSpacing: 8, children: [
        Chip(label: Text('Results: ${result['result_count'] ?? rows.length}')),
        Chip(label: Text('Source: ${widget.response['execution_source'] ?? '-'}')),
        if (contextKey != null) Chip(label: Text('Context: $contextKey')),
        Chip(label: Text('Grid rows: ${rows.length}')),
      ]),
      if (summary.trim().isNotEmpty) ...[
        const SizedBox(height: 12),
        _NarrativeSummary(summary: summary, expanded: _summaryExpanded, onToggle: () => setState(() => _summaryExpanded = !_summaryExpanded)),
      ],
      const SizedBox(height: 12),
      Wrap(spacing: 8, children: [
        OutlinedButton(onPressed: () => widget.onJson('Structured query', widget.response['structured_query'] ?? {}), child: const Text('Structured query')),
        OutlinedButton(onPressed: () => widget.onJson('Interpretation', widget.response['interpretation'] ?? {}), child: const Text('Interpretation')),
        OutlinedButton(onPressed: () => widget.onJson('Diagnostics', result['diagnostics'] ?? {}), child: const Text('Diagnostics')),
        OutlinedButton(onPressed: () => widget.onJson('Raw JSON', widget.response), child: const Text('Raw JSON')),
      ]),
      const SizedBox(height: 12),
      TrustVaultDataGrid(
        title: 'Search results',
        subtitle: 'Click a row to preview evidence or open the entity context.',
        rows: rows,
        columns: _columns(),
        initialSortColumnKey: 'entity_external_id',
        onRowTap: (row) => widget.onOpenRow(row),
        exportFilename: 'trustvault-search-results.csv',
        emptyText: 'No rows returned.',
        height: 620,
        dense: true,
      ),
    ]);
  }

  Map<String, dynamic> _flattenRow(Map<String, dynamic> row) {
    final metadata = row['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final nested = metadata['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    return <String, dynamic>{
      ...row,
      'category': row['category'] ?? metadata['category'] ?? nested['category'],
      'document_type': row['document_type'] ?? metadata['document_type'] ?? nested['document_type'],
      'risk_rating': row['risk_rating'] ?? metadata['risk_rating'] ?? nested['risk_rating'],
      'jurisdiction': row['jurisdiction'] ?? metadata['jurisdiction'] ?? nested['jurisdiction'],
      'retention_class': row['retention_class'] ?? metadata['retention_class'] ?? nested['retention_class'],
      'legal_hold_status': row['legal_hold_status'] ?? metadata['legal_hold_status'] ?? nested['legal_hold_status'],
      'snippet': row['snippet'] ?? row['text_content'] ?? row['status'] ?? row['summary_type'] ?? '',
    };
  }

  List<TrustVaultDataGridColumn> _columns() => const [
        TrustVaultDataGridColumn(key: 'entity_external_id', label: 'Entity', width: 130),
        TrustVaultDataGridColumn(key: 'entity_display_name', label: 'Name', width: 220),
        TrustVaultDataGridColumn(key: 'risk_rating', label: 'Risk', width: 90),
        TrustVaultDataGridColumn(key: 'jurisdiction', label: 'Jurisdiction', width: 130),
        TrustVaultDataGridColumn(key: 'filename', label: 'Filename', width: 260),
        TrustVaultDataGridColumn(key: 'category', label: 'Category', width: 160),
        TrustVaultDataGridColumn(key: 'document_type', label: 'Document type', width: 180),
        TrustVaultDataGridColumn(key: 'source_system', label: 'Source', width: 160),
        TrustVaultDataGridColumn(key: 'match_score', label: 'Score', width: 80),
        TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 120, visibleByDefault: false),
        TrustVaultDataGridColumn(key: 'rule_key', label: 'Rule key', width: 180, visibleByDefault: false),
        TrustVaultDataGridColumn(key: 'missing_evidence_type', label: 'Missing evidence', width: 180, visibleByDefault: false),
        TrustVaultDataGridColumn(key: 'sha256', label: 'SHA-256', width: 320, visibleByDefault: false),
        TrustVaultDataGridColumn(key: 'retention_class', label: 'Retention class', width: 160, visibleByDefault: false),
        TrustVaultDataGridColumn(key: 'legal_hold_status', label: 'Legal hold', width: 130, visibleByDefault: false),
        TrustVaultDataGridColumn(key: 'snippet', label: 'Snippet / status', width: 520),
      ];

  String _normaliseSummary(String value) {
    final text = value.replaceAll('customers', 'entities').replaceAll('customer', 'entity').trim();
    if (text.length <= 2400) return text;
    return '${text.substring(0, 2400)}\n\n[Summary truncated in the page view. Use Raw JSON if you need the full model response.]';
  }
}

class _NarrativeSummary extends StatelessWidget {
  const _NarrativeSummary({required this.summary, required this.expanded, required this.onToggle});
  final String summary;
  final bool expanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final maxHeight = expanded ? 260.0 : 96.0;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.summarize_outlined, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text('AI narrative summary', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700))),
          TextButton(onPressed: onToggle, child: Text(expanded ? 'Collapse' : 'Expand')),
        ]),
        AnimatedContainer(duration: const Duration(milliseconds: 150), constraints: BoxConstraints(maxHeight: maxHeight), child: Scrollbar(thumbVisibility: expanded, child: SingleChildScrollView(child: SelectableText(summary)))),
      ]),
    );
  }
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
    if (kind == 'pdf') return EvidencePdfViewer(apiClient: apiClient, evidenceObjectId: objectId);
    final text = preview['safe_preview'] ?? preview['text_preview'];
    if (kind == 'eml' || kind == 'text') return SingleChildScrollView(child: SelectableText('$text'));
    return Center(child: Text('No inline preview is available for ${preview['content_type'] ?? 'this file type'}'));
  }
}

class _JsonPanel extends StatelessWidget {
  const _JsonPanel({required this.value});
  final Object value;
  @override
  Widget build(BuildContext context) => DecoratedBox(
        decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(width: 1400, child: SingleChildScrollView(padding: const EdgeInsets.all(16), child: SelectableText(const JsonEncoder.withIndent('  ').convert(value), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace')))),
        ),
      );
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) => Card(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.manage_search_outlined, size: 56, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 12),
              Text('Search evidence', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              const Text('Choose the search context, ask a question, select all entities or one entity, then run Search.'),
            ]),
          ),
        ),
      );
}
