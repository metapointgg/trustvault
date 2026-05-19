import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/trustvault_data_grid.dart';

class CompletenessScreen extends StatefulWidget {
  const CompletenessScreen({super.key});

  @override
  State<CompletenessScreen> createState() => _CompletenessScreenState();
}

class _CompletenessScreenState extends State<CompletenessScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();

  late Future<_CompletenessViewModel> _future;
  _CompletenessViewModel? _lastData;
  String _riskRating = 'All';
  String _jurisdiction = 'All';
  String _entityMode = 'All entities';
  String? _selectedEntityExternalId;
  bool _includeAiSummary = false;
  int _loadGeneration = 0;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_CompletenessViewModel> _load() async {
    final generation = ++_loadGeneration;
    final entityExternalId =
        _entityMode == 'Selected entity' ? _selectedEntityExternalId : null;
    final responses = await Future.wait<dynamic>([
      _apiClient.getCustomers(limit: 1000),
      _apiClient.getCompletenessSummary(
        riskRating: _riskRating,
        jurisdiction: _jurisdiction,
        entityExternalId: entityExternalId,
        limit: 1000,
      ),
    ]);
    final entities =
        (responses[0] as List<dynamic>).cast<Map<String, dynamic>>();
    final summary = responses[1] as Map<String, dynamic>;
    final rawRows = (summary['rows'] ?? summary['results']) as List<dynamic>? ??
        <dynamic>[];
    final rows = rawRows
        .cast<Map<String, dynamic>>()
        .map(_normaliseCompletenessRow)
        .where(_rowMatchesFilters)
        .toList();

    Map<String, dynamic>? aiSummary;
    if (_includeAiSummary) {
      final query = _buildCompletenessQuery();
      aiSummary = await _apiClient.executeQuery(
          query: query, mode: 'ai', includeAiSummary: true, limit: 500);
    }

    final model = _CompletenessViewModel(
      allEntities: entities,
      filteredEntities: _filteredEntitiesForFilters(entities),
      rows: rows,
      evaluatedCount: _entityIds(rows).length,
      completeCount: _completeEntityCount(rows),
      incompleteCount: _incompleteEntityCount(rows),
      missingEvidenceItems: rows
          .where((row) =>
              '${row['rule_status'] ?? row['status']}'.toLowerCase() ==
              'missing')
          .length,
      aiSummary: aiSummary,
      rulesetName: '${summary['ruleset_name'] ?? '-'}',
      rulesetVersion: '${summary['ruleset_version'] ?? '-'}',
    );
    if (mounted && generation == _loadGeneration) {
      _lastData = model;
    }
    return model;
  }

  Map<String, dynamic> _normaliseCompletenessRow(Map<String, dynamic> row) {
    return <String, dynamic>{
      ...row,
      'rule_status': row['rule_status'] ?? row['status'],
    };
  }

  bool _rowMatchesFilters(Map<String, dynamic> row) {
    final riskOk = _riskRating == 'All' ||
        _normaliseFilterValue(row['risk_rating']) ==
            _normaliseFilterValue(_riskRating);
    final jurisdictionOk = _jurisdiction == 'All' ||
        _normaliseFilterValue(row['jurisdiction']) ==
            _normaliseFilterValue(_jurisdiction);
    final entityOk = _entityMode == 'All entities' ||
        row['entity_external_id'] == _selectedEntityExternalId;
    return riskOk && jurisdictionOk && entityOk;
  }

  String _normaliseFilterValue(Object? value) =>
      '$value'.trim().toLowerCase().replaceAll(RegExp(r'\s+'), ' ');

  Set<String> _entityIds(List<Map<String, dynamic>> rows) {
    return rows
        .map((row) => '${row['entity_id'] ?? row['entity_external_id'] ?? ''}')
        .where((id) => id.isNotEmpty)
        .toSet();
  }

  int _incompleteEntityCount(List<Map<String, dynamic>> rows) {
    return rows
        .where((row) =>
            '${row['rule_status'] ?? row['status']}'.toLowerCase() == 'missing')
        .map((row) => '${row['entity_id'] ?? row['entity_external_id'] ?? ''}')
        .where((id) => id.isNotEmpty)
        .toSet()
        .length;
  }

  int _completeEntityCount(List<Map<String, dynamic>> rows) {
    return _entityIds(rows).length - _incompleteEntityCount(rows);
  }

  List<Map<String, dynamic>> _filteredEntitiesForFilters(
      List<Map<String, dynamic>> entities) {
    return entities.where((entity) {
      final riskOk = _riskRating == 'All' ||
          _normaliseFilterValue(entity['risk_rating']) ==
              _normaliseFilterValue(_riskRating);
      final jurisdictionOk = _jurisdiction == 'All' ||
          _normaliseFilterValue(entity['jurisdiction']) ==
              _normaliseFilterValue(_jurisdiction);
      final entityOk = _entityMode == 'All entities' ||
          entity['external_id'] == _selectedEntityExternalId;
      return riskOk && jurisdictionOk && entityOk;
    }).toList();
  }

  String _buildCompletenessQuery() {
    final parts = <String>['Check evidence completeness'];
    if (_entityMode == 'Selected entity' && _selectedEntityExternalId != null) {
      parts.add('for $_selectedEntityExternalId');
    } else {
      if (_riskRating != 'All') {
        parts.add('for ${_riskRating.toLowerCase()} risk entities');
      }
      if (_jurisdiction != 'All') parts.add('in $_jurisdiction');
    }
    return parts.join(' ');
  }

  void _refresh() {
    setState(() => _future = _load());
  }

  void _setFilter(VoidCallback update) {
    update();
    if (_entityMode == 'All entities') _selectedEntityExternalId = null;
    if (_entityMode == 'Selected entity' && _selectedEntityExternalId == null) {
      final first = _lastData?.filteredEntities.firstOrNull ??
          _lastData?.allEntities.firstOrNull;
      if (first != null) _selectedEntityExternalId = '${first['external_id']}';
    }
    setState(() => _future = _load());
  }

  List<String> _values(List<Map<String, dynamic>> rows, String key) {
    final values = rows
        .map((row) => '${row[key] ?? ''}')
        .where((value) => value.trim().isNotEmpty)
        .toSet()
        .toList()
      ..sort();
    return ['All', ...values];
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_CompletenessViewModel>(
      future: _future,
      builder: (context, snapshot) {
        final data = snapshot.data ?? _lastData;
        final loading = snapshot.connectionState != ConnectionState.done;
        final entities = data?.allEntities ?? <Map<String, dynamic>>[];
        final filteredEntities =
            data?.filteredEntities ?? <Map<String, dynamic>>[];
        return Scrollbar(
          thumbVisibility: true,
          child: SingleChildScrollView(
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
                          Text('Completeness',
                              style: Theme.of(context)
                                  .textTheme
                                  .displaySmall
                                  ?.copyWith(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 8),
                          const Text(
                              'Evaluate required evidence by risk rating, jurisdiction and entity. The checklist and ruleset remain the source of truth.'),
                        ],
                      ),
                    ),
                    if (loading)
                      const Padding(
                          padding: EdgeInsets.only(right: 12),
                          child: SizedBox(
                              width: 22,
                              height: 22,
                              child:
                                  CircularProgressIndicator(strokeWidth: 2))),
                    OutlinedButton.icon(
                        onPressed: _refresh,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Refresh')),
                  ],
                ),
                const SizedBox(height: 16),
                _FilterBar(
                  riskValues: _values(entities, 'risk_rating'),
                  jurisdictionValues: _values(entities, 'jurisdiction'),
                  entities: _entityMode == 'Selected entity'
                      ? filteredEntities
                      : entities,
                  riskRating: _riskRating,
                  jurisdiction: _jurisdiction,
                  entityMode: _entityMode,
                  selectedEntityExternalId: _selectedEntityExternalId,
                  includeAiSummary: _includeAiSummary,
                  onRiskChanged: (value) =>
                      _setFilter(() => _riskRating = value),
                  onJurisdictionChanged: (value) =>
                      _setFilter(() => _jurisdiction = value),
                  onEntityModeChanged: (value) =>
                      _setFilter(() => _entityMode = value),
                  onEntityChanged: (value) =>
                      _setFilter(() => _selectedEntityExternalId = value),
                  onAiSummaryChanged: (value) =>
                      _setFilter(() => _includeAiSummary = value),
                ),
                const SizedBox(height: 16),
                if (snapshot.hasError && data == null)
                  SizedBox(
                      height: 500,
                      child: Center(
                          child: Text(
                              'Unable to load completeness data: ${snapshot.error}')))
                else if (data == null)
                  const SizedBox(
                      height: 500,
                      child: Center(child: CircularProgressIndicator()))
                else ...[
                  _CompletenessCards(data: data),
                  const SizedBox(height: 8),
                  Text('Ruleset: ${data.rulesetName} v${data.rulesetVersion}',
                      style: Theme.of(context).textTheme.bodySmall),
                  const SizedBox(height: 16),
                  if (_includeAiSummary) ...[
                    _AiCompletenessSummary(response: data.aiSummary),
                    const SizedBox(height: 16),
                  ],
                  TrustVaultDataGrid(
                    title: 'Completeness result set',
                    subtitle:
                        'Rule-level completeness rows. Missing rows are highlighted and can be searched, sorted, filtered by visible columns and exported.',
                    rows: data.rows,
                    columns: _columns(context),
                    initialSortColumnKey: 'entity_external_id',
                    exportFilename: 'trustvault-completeness.csv',
                    emptyText:
                        'No completeness rows match the selected filters.',
                    height: 620,
                    dense: true,
                    isLoading: loading,
                    loadingText: 'Updating completeness grid...',
                  ),
                  const SizedBox(height: 32),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  List<TrustVaultDataGridColumn> _columns(BuildContext context) {
    return [
      const TrustVaultDataGridColumn(
          key: 'entity_external_id', label: 'Entity ID', width: 120),
      const TrustVaultDataGridColumn(
          key: 'entity_display_name', label: 'Entity name', width: 220),
      const TrustVaultDataGridColumn(
          key: 'entity_type', label: 'Entity type', width: 130),
      const TrustVaultDataGridColumn(
          key: 'risk_rating', label: 'Risk rating', width: 110),
      const TrustVaultDataGridColumn(
          key: 'jurisdiction', label: 'Jurisdiction', width: 140),
      TrustVaultDataGridColumn(
          key: 'rule_status',
          label: 'Rule status',
          width: 120,
          cellBuilder: (row) =>
              _StatusPill(status: '${row['rule_status'] ?? '-'}')),
      const TrustVaultDataGridColumn(
          key: 'rule_key', label: 'Rule key', width: 180),
      const TrustVaultDataGridColumn(
          key: 'category', label: 'Category', width: 160),
      const TrustVaultDataGridColumn(
          key: 'document_type', label: 'Document type', width: 180),
      const TrustVaultDataGridColumn(
          key: 'completeness_score', label: 'Score', width: 80),
      const TrustVaultDataGridColumn(
          key: 'required_count',
          label: 'Required',
          width: 90,
          visibleByDefault: false),
      const TrustVaultDataGridColumn(
          key: 'present_count',
          label: 'Present',
          width: 90,
          visibleByDefault: false),
      const TrustVaultDataGridColumn(
          key: 'missing_count', label: 'Missing', width: 90),
      const TrustVaultDataGridColumn(
          key: 'matched_filename', label: 'Matched filename', width: 260),
      const TrustVaultDataGridColumn(
          key: 'matched_evidence_object_id',
          label: 'Matched evidence object',
          width: 300,
          visibleByDefault: false),
      const TrustVaultDataGridColumn(
          key: 'ruleset_id',
          label: 'Ruleset',
          width: 260,
          visibleByDefault: false),
    ];
  }
}

class _FilterBar extends StatelessWidget {
  const _FilterBar(
      {required this.riskValues,
      required this.jurisdictionValues,
      required this.entities,
      required this.riskRating,
      required this.jurisdiction,
      required this.entityMode,
      required this.selectedEntityExternalId,
      required this.includeAiSummary,
      required this.onRiskChanged,
      required this.onJurisdictionChanged,
      required this.onEntityModeChanged,
      required this.onEntityChanged,
      required this.onAiSummaryChanged});

  final List<String> riskValues;
  final List<String> jurisdictionValues;
  final List<Map<String, dynamic>> entities;
  final String riskRating;
  final String jurisdiction;
  final String entityMode;
  final String? selectedEntityExternalId;
  final bool includeAiSummary;
  final ValueChanged<String> onRiskChanged;
  final ValueChanged<String> onJurisdictionChanged;
  final ValueChanged<String> onEntityModeChanged;
  final ValueChanged<String?> onEntityChanged;
  final ValueChanged<bool> onAiSummaryChanged;

  @override
  Widget build(BuildContext context) {
    final selectedEntityIsValid = selectedEntityExternalId == null ||
        entities
            .any((entity) => entity['external_id'] == selectedEntityExternalId);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 12,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SizedBox(
                width: 200,
                child: DropdownButtonFormField<String>(
                    value: riskValues.contains(riskRating) ? riskRating : 'All',
                    decoration: const InputDecoration(
                        labelText: 'Risk rating', border: OutlineInputBorder()),
                    items: riskValues
                        .map((value) =>
                            DropdownMenuItem(value: value, child: Text(value)))
                        .toList(),
                    onChanged: (value) => onRiskChanged(value ?? 'All'))),
            SizedBox(
                width: 220,
                child: DropdownButtonFormField<String>(
                    value: jurisdictionValues.contains(jurisdiction)
                        ? jurisdiction
                        : 'All',
                    decoration: const InputDecoration(
                        labelText: 'Jurisdiction',
                        border: OutlineInputBorder()),
                    items: jurisdictionValues
                        .map((value) =>
                            DropdownMenuItem(value: value, child: Text(value)))
                        .toList(),
                    onChanged: (value) =>
                        onJurisdictionChanged(value ?? 'All'))),
            SizedBox(
                width: 300,
                child: SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(
                          value: 'All entities',
                          label: Text('All entities'),
                          icon: Icon(Icons.groups_outlined)),
                      ButtonSegment(
                          value: 'Selected entity',
                          label: Text('Selected entity'),
                          icon: Icon(Icons.business_outlined))
                    ],
                    selected: <String>{
                      entityMode
                    },
                    onSelectionChanged: (value) =>
                        onEntityModeChanged(value.first))),
            SizedBox(
              width: 360,
              child: DropdownButtonFormField<String>(
                value: selectedEntityIsValid ? selectedEntityExternalId : null,
                decoration: const InputDecoration(
                    labelText: 'Entity', border: OutlineInputBorder()),
                items: entities.map((entity) {
                  final externalId = '${entity['external_id']}';
                  return DropdownMenuItem(
                      value: externalId,
                      child: Text(
                          '$externalId · ${entity['display_name'] ?? '-'}',
                          overflow: TextOverflow.ellipsis));
                }).toList(),
                onChanged:
                    entityMode == 'Selected entity' ? onEntityChanged : null,
              ),
            ),
            SizedBox(
                width: 260,
                child: SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('AI summary'),
                    subtitle: const Text('Local narrative'),
                    value: includeAiSummary,
                    onChanged: onAiSummaryChanged)),
          ],
        ),
      ),
    );
  }
}

class _CompletenessCards extends StatelessWidget {
  const _CompletenessCards({required this.data});
  final _CompletenessViewModel data;

  @override
  Widget build(BuildContext context) {
    return Wrap(spacing: 12, runSpacing: 12, children: [
      _MetricCard(
          label: 'Entities evaluated',
          value: '${data.evaluatedCount}',
          tone: _MetricTone.neutral),
      _MetricCard(
          label: 'Complete',
          value: '${data.completeCount}',
          tone: _MetricTone.good),
      _MetricCard(
          label: 'Incomplete',
          value: '${data.incompleteCount}',
          tone:
              data.incompleteCount == 0 ? _MetricTone.good : _MetricTone.warn),
      _MetricCard(
          label: 'Missing evidence items',
          value: '${data.missingEvidenceItems}',
          tone: data.missingEvidenceItems == 0
              ? _MetricTone.good
              : _MetricTone.bad),
    ]);
  }
}

enum _MetricTone { neutral, good, warn, bad }

class _MetricCard extends StatelessWidget {
  const _MetricCard(
      {required this.label, required this.value, required this.tone});
  final String label;
  final String value;
  final _MetricTone tone;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final colour = switch (tone) {
      _MetricTone.good => scheme.primaryContainer,
      _MetricTone.warn => scheme.tertiaryContainer,
      _MetricTone.bad => scheme.errorContainer,
      _MetricTone.neutral => scheme.surfaceContainerHighest,
    };
    return SizedBox(
        width: 240,
        child: Card(
            color: colour,
            child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(value,
                          style: Theme.of(context)
                              .textTheme
                              .headlineMedium
                              ?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 4),
                      Text(label)
                    ]))));
  }
}

class _AiCompletenessSummary extends StatelessWidget {
  const _AiCompletenessSummary({required this.response});
  final Map<String, dynamic>? response;

  @override
  Widget build(BuildContext context) {
    final aiSummary = response?['ai_summary'] as Map<String, dynamic>?;
    final summary = '${aiSummary?['summary'] ?? ''}'.trim();
    final warning = '${aiSummary?['warning'] ?? ''}'.trim();
    final text = summary.isNotEmpty ? summary : warning;
    return Card(
        child: Padding(
            padding: const EdgeInsets.all(18),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Icon(Icons.psychology_alt_outlined),
                const SizedBox(width: 8),
                Expanded(
                    child: Text('AI completeness summary',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(fontWeight: FontWeight.w700))),
                if (aiSummary != null)
                  Chip(
                      label: Text(aiSummary['ai_used_for_summary'] == true
                          ? 'AI'
                          : 'Deterministic'))
              ]),
              const SizedBox(height: 4),
              const Text(
                  'Generated locally from the completeness result set. The checklist and ruleset remain the source of truth.'),
              const SizedBox(height: 12),
              if (text.isEmpty)
                const Text('No summary returned for the current filters.')
              else
                SizedBox(
                    height: 220,
                    child: Scrollbar(
                        thumbVisibility: true,
                        child: SingleChildScrollView(
                            child: SelectableText(text)))),
            ])));
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final normalised = status.toLowerCase();
    final positive = normalised == 'present' ||
        normalised == 'complete' ||
        normalised == 'matched';
    final colour = positive ? scheme.primaryContainer : scheme.errorContainer;
    final textColour =
        positive ? scheme.onPrimaryContainer : scheme.onErrorContainer;
    return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999), color: colour),
        child: Text(status,
            style: TextStyle(color: textColour, fontWeight: FontWeight.w700)));
  }
}

class _CompletenessViewModel {
  const _CompletenessViewModel(
      {required this.allEntities,
      required this.filteredEntities,
      required this.rows,
      required this.evaluatedCount,
      required this.completeCount,
      required this.incompleteCount,
      required this.missingEvidenceItems,
      required this.aiSummary,
      required this.rulesetName,
      required this.rulesetVersion});

  final List<Map<String, dynamic>> allEntities;
  final List<Map<String, dynamic>> filteredEntities;
  final List<Map<String, dynamic>> rows;
  final int evaluatedCount;
  final int completeCount;
  final int incompleteCount;
  final int missingEvidenceItems;
  final Map<String, dynamic>? aiSummary;
  final String rulesetName;
  final String rulesetVersion;
}
