import 'dart:convert';

import 'package:flutter/material.dart';

import '../../shared/trustvault_data_grid.dart';

class SearchResultPanel extends StatefulWidget {
  const SearchResultPanel({
    super.key,
    required this.response,
    required this.onOpenRow,
    required this.onPreview,
    required this.onJson,
  });

  final Map<String, dynamic> response;
  final Future<void> Function(Map<String, dynamic>) onOpenRow;
  final Future<void> Function(Map<String, dynamic>) onPreview;
  final void Function(String, Object) onJson;

  @override
  State<SearchResultPanel> createState() => _SearchResultPanelState();
}

class _SearchResultPanelState extends State<SearchResultPanel> {
  bool _summaryExpanded = false;

  @override
  Widget build(BuildContext context) {
    final result = widget.response['result'] is Map<String, dynamic>
        ? widget.response['result'] as Map<String, dynamic>
        : widget.response;
    final rows = (result['results'] as List<dynamic>? ?? <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .map(_flattenRow)
        .toList();
    final executionSource = '${widget.response['execution_source'] ?? ''}';
    final resultType = _resultType(executionSource, rows);
    final contextKey = ((widget.response['interpretation'] as Map<String, dynamic>?)?['active_industry_context'] as Map<String, dynamic>?)?['industry_key'];
    final deterministicSummary = _deterministicSummary(resultType, rows, result, executionSource);
    final rawSummary = '${(widget.response['ai_summary'] as Map<String, dynamic>?)?['summary'] ?? ''}';
    final summary = _normaliseSummary(rawSummary.trim().isNotEmpty ? rawSummary : deterministicSummary);

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(spacing: 8, runSpacing: 8, children: [
        Chip(label: Text('Results: ${result['result_count'] ?? rows.length}')),
        Chip(label: Text('Source: ${widget.response['execution_source'] ?? '-'}')),
        Chip(label: Text('View: ${_label(resultType)}')),
        if (contextKey != null) Chip(label: Text('Context: $contextKey')),
        Chip(label: Text('Rows: ${rows.length}')),
      ]),
      if (summary.trim().isNotEmpty) ...[
        const SizedBox(height: 12),
        _NarrativeSummary(summary: summary, expanded: _summaryExpanded, onToggle: () => setState(() => _summaryExpanded = !_summaryExpanded)),
      ],
      const SizedBox(height: 12),
      Wrap(spacing: 8, runSpacing: 8, children: [
        OutlinedButton(onPressed: () => widget.onJson('Structured query', widget.response['structured_query'] ?? {}), child: const Text('Structured query')),
        OutlinedButton(onPressed: () => widget.onJson('Interpretation', widget.response['interpretation'] ?? {}), child: const Text('Interpretation')),
        OutlinedButton(onPressed: () => widget.onJson('Diagnostics', result['diagnostics'] ?? {}), child: const Text('Diagnostics')),
        OutlinedButton(onPressed: () => widget.onJson('Raw JSON', widget.response), child: const Text('Raw JSON')),
      ]),
      const SizedBox(height: 12),
      _typedPresenter(resultType, rows, result),
    ]);
  }

  Widget _typedPresenter(String resultType, List<Map<String, dynamic>> rows, Map<String, dynamic> result) {
    switch (resultType) {
      case 'archive_status':
        return _ArchiveStatusPresenter(rows: rows, onJson: widget.onJson);
      case 'entity_discovery':
        return _TypedGrid(
          title: 'Matching entities',
          subtitle: 'Entities matching the interpreted filters. Click a row to open the entity context.',
          rows: rows,
          columns: _entityColumns,
          initialSortColumnKey: 'entity_external_id',
          onRowTap: widget.onOpenRow,
        );
      case 'missing_evidence':
        return _TypedGrid(
          title: 'Missing evidence',
          subtitle: 'Required evidence that is missing for the matching entity cohort.',
          rows: rows,
          columns: _missingEvidenceColumns,
          initialSortColumnKey: 'entity_external_id',
          onRowTap: widget.onOpenRow,
        );
      case 'entity_summary':
        return _EntitySummaryPresenter(rows: rows, onJson: widget.onJson);
      case 'evidence_count':
        return _TypedGrid(
          title: 'Evidence counts',
          subtitle: 'Evidence grouped by category and document type.',
          rows: rows,
          columns: _evidenceCountColumns,
          initialSortColumnKey: 'category',
          onRowTap: (_) async {},
        );
      case 'container_version':
        return _TypedGrid(
          title: 'FITS containers',
          subtitle: 'FITS container versions available for the selected entity.',
          rows: rows,
          columns: _containerColumns,
          initialSortColumnKey: 'version_number',
          onRowTap: (_) async {},
        );
      default:
        return _TypedGrid(
          title: 'Evidence results',
          subtitle: 'Evidence records matching the interpreted query. Click a row to preview evidence or open the entity context.',
          rows: rows,
          columns: _evidenceColumns,
          initialSortColumnKey: 'entity_external_id',
          onRowTap: widget.onOpenRow,
        );
    }
  }

  String _resultType(String executionSource, List<Map<String, dynamic>> rows) {
    if (executionSource == 'archive_status') return 'archive_status';
    final types = rows.map((row) => '${row['summary_type'] ?? ''}').where((value) => value.isNotEmpty).toSet();
    if (types.contains('archive_status')) return 'archive_status';
    if (types.contains('entity_summary')) return 'entity_summary';
    if (types.contains('evidence_count')) return 'evidence_count';
    if (types.contains('container_version')) return 'container_version';
    if (types.contains('missing_evidence') || executionSource == 'completeness_rules') return 'missing_evidence';
    if (types.contains('entity_discovery') || executionSource == 'entity_metadata') return 'entity_discovery';
    return 'evidence_search';
  }

  Map<String, dynamic> _flattenRow(Map<String, dynamic> row) {
    final metadata = row['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final nested = metadata['metadata'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final metadataJson = row['metadata_json'] as Map<String, dynamic>? ?? <String, dynamic>{};
    return <String, dynamic>{
      ...row,
      'entity_external_id': row['entity_external_id'] ?? row['external_id'],
      'entity_display_name': row['entity_display_name'] ?? row['display_name'],
      'category': row['category'] ?? metadata['category'] ?? nested['category'],
      'document_type': row['document_type'] ?? metadata['document_type'] ?? nested['document_type'],
      'risk_rating': row['risk_rating'] ?? metadata['risk_rating'] ?? nested['risk_rating'] ?? metadataJson['risk_rating'],
      'jurisdiction': row['jurisdiction'] ?? metadata['jurisdiction'] ?? nested['jurisdiction'] ?? metadataJson['jurisdiction'],
      'industry_pack': row['industry_pack'] ?? metadataJson['industry_pack'] ?? metadataJson['demo_archive_key'],
      'retention_class': row['retention_class'] ?? metadata['retention_class'] ?? nested['retention_class'],
      'legal_hold_status': row['legal_hold_status'] ?? metadata['legal_hold_status'] ?? nested['legal_hold_status'],
      'department': row['department'] ?? metadataJson['department'],
      'responsible_person': row['responsible_person'] ?? metadataJson['responsible_person'],
      'supplier_category': row['supplier_category'] ?? metadataJson['supplier_category'],
      'criticality': row['criticality'] ?? metadataJson['criticality'],
      'snippet': row['snippet'] ?? row['text_content'] ?? row['status'] ?? row['summary_type'] ?? '',
    };
  }

  String _deterministicSummary(String type, List<Map<String, dynamic>> rows, Map<String, dynamic> result, String executionSource) {
    if (rows.isEmpty) return 'No rows were returned from $executionSource.';
    switch (type) {
      case 'archive_status':
        final row = rows.first;
        return 'Archive status: ${row['entity_count'] ?? 0} entities, ${row['current_fits_container_count'] ?? 0} current FITS containers and ${row['fits_index_entry_count'] ?? 0} indexed evidence objects. Failed jobs: ${row['failed_jobs'] ?? 0}. Integrity issues: ${row['integrity_issue_count'] ?? 0}.';
      case 'entity_discovery':
        return 'Found ${rows.length} matching ${rows.length == 1 ? 'entity' : 'entities'}: ${_entityList(rows)}.';
      case 'missing_evidence':
        return '${rows.length} missing evidence ${rows.length == 1 ? 'item' : 'items'} found: ${_missingList(rows)}.';
      case 'entity_summary':
        final row = rows.first;
        return '${row['entity_external_id'] ?? '-'} ${row['entity_display_name'] ?? ''}: ${row['indexed_evidence_count'] ?? 0} indexed evidence objects across ${row['container_count'] ?? 0} FITS container(s).';
      case 'evidence_count':
        return 'Evidence counts returned across ${rows.length} category/document type grouping(s).';
      case 'container_version':
        return '${rows.length} FITS container ${rows.length == 1 ? 'version is' : 'versions are'} available for the selected entity.';
      default:
        final entityCount = rows.map((row) => '${row['entity_external_id'] ?? ''}').where((value) => value.isNotEmpty).toSet().length;
        return 'Found ${rows.length} evidence ${rows.length == 1 ? 'row' : 'rows'} across $entityCount ${entityCount == 1 ? 'entity' : 'entities'}.';
    }
  }

  String _entityList(List<Map<String, dynamic>> rows) => rows.take(5).map((row) => '${row['entity_external_id'] ?? row['external_id'] ?? '-'} ${row['entity_display_name'] ?? row['display_name'] ?? ''}'.trim()).join(', ');

  String _missingList(List<Map<String, dynamic>> rows) => rows.take(5).map((row) => '${row['entity_external_id'] ?? '-'} missing ${row['document_type'] ?? row['missing_evidence_type'] ?? row['rule_key'] ?? 'evidence'}').join(', ');

  String _normaliseSummary(String value) {
    final text = value.replaceAll('customers', 'entities').replaceAll('customer', 'entity').trim();
    if (text.length <= 2400) return text;
    return '${text.substring(0, 2400)}\n\n[Summary truncated in the page view. Use Raw JSON if you need the full model response.]';
  }
}

class _TypedGrid extends StatelessWidget {
  const _TypedGrid({
    required this.title,
    required this.subtitle,
    required this.rows,
    required this.columns,
    required this.initialSortColumnKey,
    required this.onRowTap,
  });

  final String title;
  final String subtitle;
  final List<Map<String, dynamic>> rows;
  final List<TrustVaultDataGridColumn> columns;
  final String initialSortColumnKey;
  final Future<void> Function(Map<String, dynamic>) onRowTap;

  @override
  Widget build(BuildContext context) => TrustVaultDataGrid(
        title: title,
        subtitle: subtitle,
        rows: rows,
        columns: columns,
        initialSortColumnKey: initialSortColumnKey,
        onRowTap: onRowTap,
        exportFilename: 'trustvault-search-results.csv',
        emptyText: 'No rows returned.',
        height: 620,
        dense: true,
      );
}

class _ArchiveStatusPresenter extends StatelessWidget {
  const _ArchiveStatusPresenter({required this.rows, required this.onJson});

  final List<Map<String, dynamic>> rows;
  final void Function(String, Object) onJson;

  @override
  Widget build(BuildContext context) {
    final row = rows.isNotEmpty ? rows.first : <String, dynamic>{};
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(spacing: 12, runSpacing: 12, children: [
        _MetricCard(label: 'Entities', value: row['entity_count']),
        _MetricCard(label: 'Current FITS containers', value: row['current_fits_container_count']),
        _MetricCard(label: 'Indexed evidence objects', value: row['fits_index_entry_count']),
        _MetricCard(label: 'Completeness exceptions', value: row['completeness_exception_count']),
        _MetricCard(label: 'Uncategorised', value: row['categorisation_uncategorised_count']),
        _MetricCard(label: 'Failed jobs', value: row['failed_jobs']),
      ]),
      const SizedBox(height: 12),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Archive configuration', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            _KeyValue(label: 'Storage provider', value: row['storage_provider']),
            _KeyValue(label: 'Queue provider', value: row['queue_provider']),
            _KeyValue(label: 'Source folder', value: row['source_folder']),
            _KeyValue(label: 'Containers folder', value: row['containers_folder']),
            _KeyValue(label: 'Index path', value: row['index_path']),
            _KeyValue(label: 'Exports folder', value: row['exports_folder']),
            const SizedBox(height: 8),
            Wrap(spacing: 8, children: [
              _StatusChip(label: 'FITS source of truth', value: row['fits_source_of_truth']),
              _StatusChip(label: 'Index rebuildable', value: row['index_rebuildable']),
              _StatusChip(label: 'Direct FITS search', value: row['direct_fits_search_available']),
              _StatusChip(label: 'Cross-archive index', value: row['cross_archive_index_available']),
            ]),
          ]),
        ),
      ),
      const SizedBox(height: 12),
      _TypedGrid(
        title: 'Archive status row',
        subtitle: 'The same status returned as a grid row for export and inspection.',
        rows: rows,
        columns: _archiveColumns,
        initialSortColumnKey: 'entity_external_id',
        onRowTap: (_) async {},
      ),
    ]);
  }
}

class _EntitySummaryPresenter extends StatelessWidget {
  const _EntitySummaryPresenter({required this.rows, required this.onJson});

  final List<Map<String, dynamic>> rows;
  final void Function(String, Object) onJson;

  @override
  Widget build(BuildContext context) {
    final row = rows.isNotEmpty ? rows.first : <String, dynamic>{};
    final categoryCounts = row['category_counts'] is Map<String, dynamic> ? row['category_counts'] as Map<String, dynamic> : <String, dynamic>{};
    final documentTypeCounts = row['document_type_counts'] is Map<String, dynamic> ? row['document_type_counts'] as Map<String, dynamic> : <String, dynamic>{};
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${row['entity_external_id'] ?? '-'} · ${row['entity_display_name'] ?? ''}', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Wrap(spacing: 12, runSpacing: 12, children: [
              _MetricCard(label: 'Containers', value: row['container_count']),
              _MetricCard(label: 'Indexed evidence', value: row['indexed_evidence_count']),
              _MetricCard(label: 'Latest version', value: row['latest_container_version']),
              _MetricCard(label: 'Latest status', value: row['latest_container_status']),
            ]),
            const SizedBox(height: 12),
            Wrap(spacing: 8, children: [
              OutlinedButton(onPressed: () => onJson('Category counts', categoryCounts), child: const Text('Category counts')),
              OutlinedButton(onPressed: () => onJson('Document type counts', documentTypeCounts), child: const Text('Document type counts')),
              OutlinedButton(onPressed: () => onJson('Entity metadata', row['metadata_json'] ?? {}), child: const Text('Entity metadata')),
            ]),
          ]),
        ),
      ),
      const SizedBox(height: 12),
      _TypedGrid(
        title: 'Entity summary row',
        subtitle: 'Structured entity summary returned by the query engine.',
        rows: rows,
        columns: _entitySummaryColumns,
        initialSortColumnKey: 'entity_external_id',
        onRowTap: (_) async {},
      ),
    ]);
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.label, required this.value});
  final String label;
  final Object? value;

  @override
  Widget build(BuildContext context) => Card(
        child: Container(
          width: 190,
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 6),
            Text('${value ?? '-'}', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          ]),
        ),
      );
}

class _KeyValue extends StatelessWidget {
  const _KeyValue({required this.label, required this.value});
  final String label;
  final Object? value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 170, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700))),
          Expanded(child: SelectableText('${value ?? '-'}')),
        ]),
      );
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.value});
  final String label;
  final Object? value;

  @override
  Widget build(BuildContext context) {
    final ok = value == true;
    return Chip(
      avatar: Icon(ok ? Icons.check_circle_outline : Icons.error_outline, size: 18),
      label: Text('$label: ${value ?? '-'}'),
      visualDensity: VisualDensity.compact,
    );
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
          Expanded(child: Text('Answer summary', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700))),
          TextButton(onPressed: onToggle, child: Text(expanded ? 'Collapse' : 'Expand')),
        ]),
        AnimatedContainer(duration: const Duration(milliseconds: 150), constraints: BoxConstraints(maxHeight: maxHeight), child: Scrollbar(thumbVisibility: expanded, child: SingleChildScrollView(child: SelectableText(summary)))),
      ]),
    );
  }
}

String _label(String value) => value.replaceAll('_', ' ').split(' ').map((part) => part.isEmpty ? part : '${part.substring(0, 1).toUpperCase()}${part.substring(1)}').join(' ');

const _entityColumns = [
  TrustVaultDataGridColumn(key: 'entity_external_id', label: 'Entity', width: 130),
  TrustVaultDataGridColumn(key: 'entity_display_name', label: 'Name', width: 220),
  TrustVaultDataGridColumn(key: 'entity_type', label: 'Type', width: 130),
  TrustVaultDataGridColumn(key: 'risk_rating', label: 'Risk', width: 90),
  TrustVaultDataGridColumn(key: 'jurisdiction', label: 'Jurisdiction', width: 130),
  TrustVaultDataGridColumn(key: 'industry_pack', label: 'Industry', width: 180),
  TrustVaultDataGridColumn(key: 'department', label: 'Department', width: 130, visibleByDefault: false),
  TrustVaultDataGridColumn(key: 'responsible_person', label: 'Responsible person', width: 160, visibleByDefault: false),
  TrustVaultDataGridColumn(key: 'supplier_category', label: 'Supplier category', width: 150, visibleByDefault: false),
  TrustVaultDataGridColumn(key: 'criticality', label: 'Criticality', width: 110, visibleByDefault: false),
  TrustVaultDataGridColumn(key: 'snippet', label: 'Summary', width: 520),
];

const _missingEvidenceColumns = [
  TrustVaultDataGridColumn(key: 'entity_external_id', label: 'Entity', width: 130),
  TrustVaultDataGridColumn(key: 'entity_display_name', label: 'Name', width: 220),
  TrustVaultDataGridColumn(key: 'entity_type', label: 'Type', width: 120),
  TrustVaultDataGridColumn(key: 'risk_rating', label: 'Risk', width: 90),
  TrustVaultDataGridColumn(key: 'jurisdiction', label: 'Jurisdiction', width: 130),
  TrustVaultDataGridColumn(key: 'document_type', label: 'Missing document', width: 210),
  TrustVaultDataGridColumn(key: 'rule_key', label: 'Rule', width: 180),
  TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 110),
  TrustVaultDataGridColumn(key: 'snippet', label: 'Explanation', width: 520),
];

const _evidenceColumns = [
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
  TrustVaultDataGridColumn(key: 'sha256', label: 'SHA-256', width: 320, visibleByDefault: false),
  TrustVaultDataGridColumn(key: 'snippet', label: 'Snippet / status', width: 520),
];

const _archiveColumns = [
  TrustVaultDataGridColumn(key: 'entity_external_id', label: 'Entity', width: 130),
  TrustVaultDataGridColumn(key: 'entity_display_name', label: 'Name', width: 220),
  TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 100),
  TrustVaultDataGridColumn(key: 'entity_count', label: 'Entities', width: 100),
  TrustVaultDataGridColumn(key: 'current_fits_container_count', label: 'Containers', width: 120),
  TrustVaultDataGridColumn(key: 'fits_index_entry_count', label: 'Index entries', width: 120),
  TrustVaultDataGridColumn(key: 'failed_jobs', label: 'Failed jobs', width: 100),
  TrustVaultDataGridColumn(key: 'snippet', label: 'Summary', width: 520),
];

const _entitySummaryColumns = [
  TrustVaultDataGridColumn(key: 'entity_external_id', label: 'Entity', width: 130),
  TrustVaultDataGridColumn(key: 'entity_display_name', label: 'Name', width: 220),
  TrustVaultDataGridColumn(key: 'entity_type', label: 'Type', width: 120),
  TrustVaultDataGridColumn(key: 'container_count', label: 'Containers', width: 120),
  TrustVaultDataGridColumn(key: 'indexed_evidence_count', label: 'Evidence', width: 110),
  TrustVaultDataGridColumn(key: 'latest_container_version', label: 'Latest version', width: 130),
  TrustVaultDataGridColumn(key: 'latest_container_status', label: 'Latest status', width: 130),
];

const _evidenceCountColumns = [
  TrustVaultDataGridColumn(key: 'entity_external_id', label: 'Entity', width: 130),
  TrustVaultDataGridColumn(key: 'entity_display_name', label: 'Name', width: 220),
  TrustVaultDataGridColumn(key: 'category', label: 'Category', width: 220),
  TrustVaultDataGridColumn(key: 'document_type', label: 'Document type', width: 260),
  TrustVaultDataGridColumn(key: 'evidence_count', label: 'Count', width: 100),
];

const _containerColumns = [
  TrustVaultDataGridColumn(key: 'entity_external_id', label: 'Entity', width: 130),
  TrustVaultDataGridColumn(key: 'entity_display_name', label: 'Name', width: 220),
  TrustVaultDataGridColumn(key: 'version_number', label: 'Version', width: 100),
  TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 120),
  TrustVaultDataGridColumn(key: 'evidence_object_count', label: 'Evidence objects', width: 150),
  TrustVaultDataGridColumn(key: 'size_bytes', label: 'Size bytes', width: 120),
  TrustVaultDataGridColumn(key: 'sha256', label: 'SHA-256', width: 320),
  TrustVaultDataGridColumn(key: 'created_at', label: 'Created', width: 190),
];
