import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/customer_selector_card.dart';
import '../../shared/selected_customer.dart';
import '../../shared/trustvault_data_grid.dart';

enum AssuranceKind { completeness, extraction, retention, integrity }

class AssuranceOverviewScreen extends StatefulWidget {
  const AssuranceOverviewScreen({super.key, required this.kind});

  final AssuranceKind kind;

  @override
  State<AssuranceOverviewScreen> createState() => _AssuranceOverviewScreenState();
}

class _AssuranceOverviewScreenState extends State<AssuranceOverviewScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<Map<String, dynamic>>> _allFuture;
  Future<Map<String, dynamic>>? _detailFuture;
  String? _loadedFor;

  @override
  void initState() {
    super.initState();
    SelectedCustomerController.selected.addListener(_loadDetail);
    _allFuture = _loadAllEntities();
    _loadDetail();
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_loadDetail);
    super.dispose();
  }

  String get _title {
    switch (widget.kind) {
      case AssuranceKind.completeness:
        return 'Completeness';
      case AssuranceKind.extraction:
        return 'Extraction';
      case AssuranceKind.retention:
        return 'Legal Hold & Retention';
      case AssuranceKind.integrity:
        return 'Integrity';
    }
  }

  String get _subtitle {
    switch (widget.kind) {
      case AssuranceKind.completeness:
        return 'Archive-wide required-evidence status, followed by entity drill-down.';
      case AssuranceKind.extraction:
        return 'Archive-wide extraction coverage from the search index, followed by FITS entity drill-down.';
      case AssuranceKind.retention:
        return 'Archive-wide legal-hold and retention status, followed by entity drill-down.';
      case AssuranceKind.integrity:
        return 'Archive-wide FITS integrity status, followed by entity drill-down.';
    }
  }

  Future<Map<String, dynamic>> _loadReport(String externalId) {
    switch (widget.kind) {
      case AssuranceKind.completeness:
        return _apiClient.evaluateCompleteness(externalId);
      case AssuranceKind.extraction:
        return _apiClient.getExtractionReport(externalId);
      case AssuranceKind.retention:
        return _apiClient.getEntityRetention(externalId);
      case AssuranceKind.integrity:
        return _apiClient.getEntityIntegrity(externalId);
    }
  }

  Future<List<Map<String, dynamic>>> _loadAllEntities() async {
    switch (widget.kind) {
      case AssuranceKind.completeness:
        final summary = await _apiClient.getCompletenessSummary(limit: 1000);
        final rows = (summary['rows'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
        final byEntity = <String, Map<String, dynamic>>{};
        for (final row in rows) {
          final key = '${row['entity_external_id']}';
          byEntity.putIfAbsent(key, () => {
                'id': row['entity_id'],
                'external_id': row['entity_external_id'],
                'display_name': row['entity_display_name'],
                'risk_rating': row['risk_rating'],
                'jurisdiction': row['jurisdiction'],
                'status': ((row['missing_count'] as num?)?.toInt() ?? 0) == 0 ? 'complete' : 'incomplete',
                'score': row['completeness_score'] ?? 0,
                'issue_count': row['missing_count'] ?? 0,
                'summary': 'Missing: ${row['missing_count'] ?? 0}',
              });
        }
        return byEntity.values.toList();
      case AssuranceKind.extraction:
        final summary = await _apiClient.getExtractionSummary();
        return (summary['results'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
      case AssuranceKind.retention:
        final entities = (await _apiClient.getCustomers()).cast<Map<String, dynamic>>();
        final report = await _apiClient.getRetentionReport();
        final reportEntities = (report['entities'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
        final entityByExternal = {for (final entity in entities) '${entity['external_id']}': entity};
        return reportEntities.map((entry) {
          final externalId = '${entry['entity_external_id']}';
          final entity = entityByExternal[externalId] ?? <String, dynamic>{};
          final evidence = (entry['evidence'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
          final holds = evidence.where((row) => '${row['legal_hold_status'] ?? 'none'}'.toLowerCase() != 'none').length;
          final deletionEligible = evidence.where((row) => row['deletion_eligible'] == true).length;
          return <String, dynamic>{
            ...entity,
            'id': entry['entity_id'] ?? entity['id'],
            'external_id': externalId,
            'display_name': entity['display_name'] ?? externalId,
            'status': holds > 0 ? 'hold' : 'ok',
            'score': evidence.isEmpty ? 0 : 100,
            'issue_count': holds + deletionEligible,
            'summary': '$holds holds · $deletionEligible deletion eligible',
          };
        }).toList();
      case AssuranceKind.integrity:
        final entities = (await _apiClient.getCustomers()).cast<Map<String, dynamic>>();
        final entityById = {for (final entity in entities) '${entity['id']}': entity};
        final entityByExternal = {for (final entity in entities) '${entity['external_id']}': entity};
        final summary = await _apiClient.getIntegritySummary();
        final results = (summary['results'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
        return results.map((result) {
          final entity = entityById['${result['entity_id']}'] ?? entityByExternal['${result['entity_external_id']}'] ?? <String, dynamic>{};
          final payloads = (result['payload_results'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
          final failed = payloads.where((row) => row['valid'] != true).length;
          final missingHdus = (result['missing_required_hdus'] as List<dynamic>? ?? <dynamic>[]).length;
          final errors = (result['errors'] as List<dynamic>? ?? <dynamic>[]).length;
          final overall = '${result['overall_status'] ?? 'unknown'}';
          final ok = overall == 'valid' && failed == 0 && missingHdus == 0 && errors == 0;
          return <String, dynamic>{
            ...entity,
            'id': result['entity_id'] ?? entity['id'],
            'external_id': entity['external_id'] ?? result['entity_external_id'] ?? result['entity_id'],
            'display_name': entity['display_name'] ?? result['entity_external_id'] ?? result['entity_id'] ?? '-',
            'status': overall,
            'score': ok ? 100 : 0,
            'issue_count': failed + missingHdus + errors,
            'summary': '$failed failed payloads · $missingHdus missing HDUs',
            'container_version_id': result['container_version_id'],
            'fits_opened': result['fits_opened'],
            'container_hash_matches': result['container_hash_matches'],
          };
        }).toList();
    }
  }

  List<Map<String, dynamic>> _retentionRows(Map<String, dynamic> report) {
    final entities = report['entities'] as List<dynamic>? ?? <dynamic>[];
    if (entities.isEmpty) return <Map<String, dynamic>>[];
    final evidence = (entities.first as Map<String, dynamic>)['evidence'] as List<dynamic>? ?? <dynamic>[];
    return evidence.cast<Map<String, dynamic>>();
  }

  void _refresh() {
    setState(() => _allFuture = _loadAllEntities());
    _loadDetail();
  }

  void _loadDetail() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId == null || externalId.isEmpty) {
      setState(() {
        _detailFuture = null;
        _loadedFor = null;
      });
      return;
    }
    setState(() {
      _detailFuture = _loadReport(externalId);
      _loadedFor = externalId;
    });
  }

  void _selectEntity(Map<String, dynamic> row) {
    SelectedCustomerController.select(row);
    _loadDetail();
  }

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(_title, style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)), const SizedBox(height: 8), Text(_subtitle)])),
            OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
          ]),
          const SizedBox(height: 16),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _allFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) return const SizedBox(height: 520, child: Center(child: CircularProgressIndicator()));
              if (snapshot.hasError) return SizedBox(height: 520, child: Center(child: Text('Unable to load assurance summary: ${snapshot.error}')));
              final rows = snapshot.data ?? <Map<String, dynamic>>[];
              return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _SummaryCards(kind: widget.kind, rows: rows),
                const SizedBox(height: 16),
                _AllEntitiesGrid(kind: widget.kind, rows: rows, onSelected: _selectEntity),
                const SizedBox(height: 16),
                Text('Entity detail', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                CustomerSelectorCard(title: 'Search by entity name / ID', subtitle: 'Select an entity to view assurance detail.', onChanged: (_) => _loadDetail()),
                const SizedBox(height: 12),
                _DetailPanel(kind: widget.kind, future: _detailFuture, loadedFor: _loadedFor, retentionRows: _retentionRows),
                const SizedBox(height: 32),
              ]);
            },
          ),
        ]),
      ),
    );
  }
}

class _SummaryCards extends StatelessWidget {
  const _SummaryCards({required this.kind, required this.rows});
  final AssuranceKind kind;
  final List<Map<String, dynamic>> rows;
  @override
  Widget build(BuildContext context) {
    final ok = rows.where((row) => (row['score'] as num? ?? 0) >= 100 && row['status'] != 'hold').length;
    final avg = rows.isEmpty ? 0 : (rows.map((row) => (row['score'] as num? ?? 0).toDouble()).reduce((a, b) => a + b) / rows.length).round();
    final issues = rows.fold<int>(0, (total, row) => total + ((row['issue_count'] as num?)?.toInt() ?? 0));
    final statusLabel = kind == AssuranceKind.retention ? '$issues legal/retention flags' : '$avg%';
    return Wrap(spacing: 12, runSpacing: 12, children: [
      _MetricCard(label: kind == AssuranceKind.retention ? 'Legal/retention flags' : 'Overall status', value: statusLabel, good: kind == AssuranceKind.retention ? issues == 0 : avg == 100),
      _MetricCard(label: 'Entities OK', value: '$ok / ${rows.length}', good: ok == rows.length),
      _MetricCard(label: 'Items requiring review', value: '$issues', good: issues == 0),
    ]);
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.label, required this.value, required this.good});
  final String label;
  final String value;
  final bool good;
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(width: 240, child: Card(color: good ? scheme.primaryContainer : scheme.errorContainer, child: Padding(padding: const EdgeInsets.all(18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(value, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)), Text(label)]))));
  }
}

class _AllEntitiesGrid extends StatelessWidget {
  const _AllEntitiesGrid({required this.kind, required this.rows, required this.onSelected});
  final AssuranceKind kind;
  final List<Map<String, dynamic>> rows;
  final ValueChanged<Map<String, dynamic>> onSelected;
  @override
  Widget build(BuildContext context) {
    return TrustVaultDataGrid(title: 'All entities', subtitle: 'Archive-wide assurance status by entity.', rows: rows, columns: _columns(), initialSortColumnKey: 'external_id', onRowTap: onSelected, exportFilename: 'trustvault-assurance-entities.csv', height: 420, dense: true);
  }

  List<TrustVaultDataGridColumn> _columns() => [
        const TrustVaultDataGridColumn(key: 'external_id', label: 'Entity', width: 130),
        const TrustVaultDataGridColumn(key: 'display_name', label: 'Name', width: 220),
        const TrustVaultDataGridColumn(key: 'risk_rating', label: 'Risk', width: 100),
        const TrustVaultDataGridColumn(key: 'jurisdiction', label: 'Jurisdiction', width: 140),
        const TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 130),
        const TrustVaultDataGridColumn(key: 'score', label: 'Score', width: 90),
        const TrustVaultDataGridColumn(key: 'issue_count', label: 'Issues', width: 90),
        const TrustVaultDataGridColumn(key: 'summary', label: 'Summary', width: 360),
        if (kind == AssuranceKind.extraction) ...const [TrustVaultDataGridColumn(key: 'indexed_entry_count', label: 'Indexed', width: 100, visibleByDefault: false), TrustVaultDataGridColumn(key: 'text_row_count', label: 'Text rows', width: 110), TrustVaultDataGridColumn(key: 'character_count', label: 'Characters', width: 120)],
        if (kind == AssuranceKind.integrity) ...const [TrustVaultDataGridColumn(key: 'container_version_id', label: 'Container', width: 260, visibleByDefault: false), TrustVaultDataGridColumn(key: 'fits_opened', label: 'FITS opened', width: 110), TrustVaultDataGridColumn(key: 'container_hash_matches', label: 'Hash matches', width: 130)],
      ];
}

class _DetailPanel extends StatelessWidget {
  const _DetailPanel({required this.kind, required this.future, required this.loadedFor, required this.retentionRows});
  final AssuranceKind kind;
  final Future<Map<String, dynamic>>? future;
  final String? loadedFor;
  final List<Map<String, dynamic>> Function(Map<String, dynamic>) retentionRows;
  @override
  Widget build(BuildContext context) {
    if (future == null) return const SizedBox(height: 260, child: Center(child: Text('Select an entity to view detail.')));
    return FutureBuilder<Map<String, dynamic>>(
      key: ValueKey('assurance-${kind.name}-$loadedFor'),
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const SizedBox(height: 360, child: Center(child: CircularProgressIndicator()));
        if (snapshot.hasError) return SizedBox(height: 360, child: Center(child: Text('Unable to load detail: ${snapshot.error}')));
        final data = snapshot.data ?? <String, dynamic>{};
        switch (kind) {
          case AssuranceKind.completeness:
            return _CompletenessTable(rows: (data['results'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>());
          case AssuranceKind.extraction:
            return _ExtractionTable(rows: (data['ocr_text'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>());
          case AssuranceKind.retention:
            return _RetentionTable(rows: retentionRows(data));
          case AssuranceKind.integrity:
            return _IntegrityTable(data: data);
        }
      },
    );
  }
}

class _CompletenessTable extends StatelessWidget {
  const _CompletenessTable({required this.rows});
  final List<Map<String, dynamic>> rows;
  @override
  Widget build(BuildContext context) => TrustVaultDataGrid(title: 'Completeness detail', rows: rows, columns: const [TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 120), TrustVaultDataGridColumn(key: 'rule_key', label: 'Rule', width: 220), TrustVaultDataGridColumn(key: 'category', label: 'Category', width: 160), TrustVaultDataGridColumn(key: 'document_type', label: 'Document type', width: 180), TrustVaultDataGridColumn(key: 'matched_evidence_object_id', label: 'Matched evidence', width: 300), TrustVaultDataGridColumn(key: 'matched_filename', label: 'Matched filename', width: 260)], exportFilename: 'trustvault-completeness-detail.csv', height: 420, dense: true);
}

class _ExtractionTable extends StatelessWidget {
  const _ExtractionTable({required this.rows});
  final List<Map<String, dynamic>> rows;
  @override
  Widget build(BuildContext context) => TrustVaultDataGrid(title: 'Extraction detail', rows: rows.map((row) => {...row, 'preview': _preview('${row['extracted_text'] ?? ''}')}).toList(), columns: const [TrustVaultDataGridColumn(key: 'filename', label: 'Filename', width: 260), TrustVaultDataGridColumn(key: 'extraction_method', label: 'Method', width: 140), TrustVaultDataGridColumn(key: 'extraction_confidence', label: 'Confidence', width: 110), TrustVaultDataGridColumn(key: 'character_count', label: 'Characters', width: 110), TrustVaultDataGridColumn(key: 'preview', label: 'Text preview', width: 520), TrustVaultDataGridColumn(key: 'object_id', label: 'Object', width: 300, visibleByDefault: false)], exportFilename: 'trustvault-extraction-detail.csv', height: 420, dense: true);
}

class _RetentionTable extends StatelessWidget {
  const _RetentionTable({required this.rows});
  final List<Map<String, dynamic>> rows;
  @override
  Widget build(BuildContext context) => TrustVaultDataGrid(title: 'Legal hold & retention detail', rows: rows, columns: const [TrustVaultDataGridColumn(key: 'filename', label: 'Filename', width: 260), TrustVaultDataGridColumn(key: 'category', label: 'Category', width: 160), TrustVaultDataGridColumn(key: 'document_type', label: 'Document type', width: 180), TrustVaultDataGridColumn(key: 'retention_class', label: 'Retention class', width: 170), TrustVaultDataGridColumn(key: 'retention_until', label: 'Retention until', width: 150), TrustVaultDataGridColumn(key: 'legal_hold_status', label: 'Legal hold', width: 130), TrustVaultDataGridColumn(key: 'deletion_eligible', label: 'Deletion eligible', width: 150), TrustVaultDataGridColumn(key: 'object_id', label: 'Object', width: 300, visibleByDefault: false)], exportFilename: 'trustvault-retention-detail.csv', height: 420, dense: true);
}

class _IntegrityTable extends StatelessWidget {
  const _IntegrityTable({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context) {
    final payloads = (data['payload_results'] as List<dynamic>? ?? data['payloads'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
    final failed = payloads.where((row) => row['status'] != 'valid' && row['valid'] != true).toList();
    final rows = failed.isEmpty ? payloads : failed;
    return TrustVaultDataGrid(title: 'Integrity detail', rows: rows, columns: const [TrustVaultDataGridColumn(key: 'hdu_name', label: 'Payload', width: 200), TrustVaultDataGridColumn(key: 'payload_hdu', label: 'Payload HDU', width: 200, visibleByDefault: false), TrustVaultDataGridColumn(key: 'filename', label: 'Filename', width: 260), TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 120), TrustVaultDataGridColumn(key: 'valid', label: 'Valid', width: 100), TrustVaultDataGridColumn(key: 'expected_sha256', label: 'Expected SHA-256', width: 320), TrustVaultDataGridColumn(key: 'actual_sha256', label: 'Actual SHA-256', width: 320), TrustVaultDataGridColumn(key: 'sha256', label: 'SHA-256', width: 320, visibleByDefault: false)], exportFilename: 'trustvault-integrity-detail.csv', height: 420, dense: true);
  }
}

String _preview(String text) => text.length <= 280 ? text : '${text.substring(0, 280)}...';
