import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/customer_selector_card.dart';
import '../../shared/selected_customer.dart';

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
        return 'Archive-wide extraction coverage and confidence, followed by entity drill-down.';
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
    final entities = (await _apiClient.getCustomers()).cast<Map<String, dynamic>>();
    final rows = <Map<String, dynamic>>[];
    for (final entity in entities) {
      try {
        final report = await _loadReport('${entity['external_id']}');
        rows.add(<String, dynamic>{...entity, '_report': report, ..._summaryFor(entity, report)});
      } catch (error) {
        rows.add(<String, dynamic>{...entity, '_report_error': '$error', 'status': 'error', 'score': 0, 'issue_count': 1});
      }
    }
    return rows;
  }

  Map<String, dynamic> _summaryFor(Map<String, dynamic> entity, Map<String, dynamic> report) {
    switch (widget.kind) {
      case AssuranceKind.completeness:
        final score = (report['score'] as num?)?.toInt() ?? 0;
        final missing = (report['missing_count'] as num?)?.toInt() ?? 0;
        return {'status': score >= 100 ? 'complete' : 'incomplete', 'score': score, 'issue_count': missing, 'summary': 'Missing: $missing'};
      case AssuranceKind.extraction:
        final rows = (report['ocr_text'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
        final lowConfidence = rows.where((row) => ((row['extraction_confidence'] as num?)?.toDouble() ?? 1) < 0.7).length;
        final totalChars = rows.fold<int>(0, (total, row) => total + ((row['character_count'] as num?)?.toInt() ?? '${row['extracted_text'] ?? ''}'.length));
        return {'status': rows.isEmpty ? 'no text' : lowConfidence > 0 ? 'review' : 'ok', 'score': rows.isEmpty ? 0 : 100, 'issue_count': lowConfidence, 'summary': '${rows.length} text rows · $totalChars chars'};
      case AssuranceKind.retention:
        final evidence = _retentionRows(report);
        final holds = evidence.where((row) => '${row['legal_hold_status'] ?? 'none'}'.toLowerCase() != 'none').length;
        final deletionEligible = evidence.where((row) => row['deletion_eligible'] == true).length;
        return {'status': holds > 0 ? 'hold' : 'ok', 'score': evidence.isEmpty ? 0 : 100, 'issue_count': holds + deletionEligible, 'summary': '$holds holds · $deletionEligible deletion eligible'};
      case AssuranceKind.integrity:
        final overall = '${report['overall_status'] ?? report['status'] ?? 'unknown'}';
        final payloads = (report['payload_results'] as List<dynamic>? ?? report['payloads'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
        final failed = payloads.where((row) => row['status'] != 'valid' && row['valid'] != true).length;
        final missingHdus = (report['missing_required_hdus'] as List<dynamic>? ?? <dynamic>[]).length;
        final ok = (overall == 'valid' || overall == 'success') && failed == 0 && missingHdus == 0;
        return {'status': ok ? 'valid' : overall, 'score': ok ? 100 : 0, 'issue_count': failed + missingHdus, 'summary': '$failed failed payloads · $missingHdus missing HDUs'};
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
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_title, style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Text(_subtitle),
            ])),
            OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
          ]),
          const SizedBox(height: 16),
          Expanded(
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _allFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError) return Center(child: Text('Unable to load assurance summary: ${snapshot.error}'));
                final rows = snapshot.data ?? <Map<String, dynamic>>[];
                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  _SummaryCards(kind: widget.kind, rows: rows),
                  const SizedBox(height: 16),
                  Expanded(flex: 2, child: _AllEntitiesGrid(rows: rows, onSelected: _selectEntity)),
                  const SizedBox(height: 16),
                  Text('Entity detail', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  CustomerSelectorCard(title: 'Search by entity name / ID', subtitle: 'Select an entity to view assurance detail.', onChanged: (_) => _loadDetail()),
                  const SizedBox(height: 12),
                  Expanded(flex: 2, child: _DetailPanel(kind: widget.kind, future: _detailFuture, loadedFor: _loadedFor, retentionRows: _retentionRows)),
                ]);
              },
            ),
          ),
        ],
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
  const _AllEntitiesGrid({required this.rows, required this.onSelected});
  final List<Map<String, dynamic>> rows;
  final ValueChanged<Map<String, dynamic>> onSelected;
  @override
  Widget build(BuildContext context) {
    return Card(child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: SingleChildScrollView(child: DataTable(showCheckboxColumn: false, columns: const [DataColumn(label: Text('Entity')), DataColumn(label: Text('Name')), DataColumn(label: Text('Risk')), DataColumn(label: Text('Jurisdiction')), DataColumn(label: Text('Status')), DataColumn(label: Text('Score')), DataColumn(label: Text('Issues')), DataColumn(label: Text('Summary')), DataColumn(label: Text('Actions'))], rows: rows.map((row) {
      final score = (row['score'] as num?)?.toInt() ?? 0;
      return DataRow(onSelectChanged: (_) => onSelected(row), color: (score >= 100 && row['status'] != 'hold') ? null : WidgetStatePropertyAll(Theme.of(context).colorScheme.errorContainer.withValues(alpha: 0.22)), cells: [DataCell(Text('${row['external_id'] ?? row['entity_external_id'] ?? '-'}')), DataCell(SizedBox(width: 220, child: Text('${row['display_name'] ?? row['entity_display_name'] ?? '-'}', overflow: TextOverflow.ellipsis))), DataCell(Text('${row['risk_rating'] ?? '-'}')), DataCell(Text('${row['jurisdiction'] ?? '-'}')), DataCell(Text('${row['status'] ?? '-'}')), DataCell(Text('$score%')), DataCell(Text('${row['issue_count'] ?? '-'}')), DataCell(SizedBox(width: 300, child: Text('${row['summary'] ?? row['_report_error'] ?? '-'}', overflow: TextOverflow.ellipsis))), DataCell(TextButton(onPressed: () => onSelected(row), child: const Text('View detail')))]);
    }).toList()))));
  }
}

class _DetailPanel extends StatelessWidget {
  const _DetailPanel({required this.kind, required this.future, required this.loadedFor, required this.retentionRows});
  final AssuranceKind kind;
  final Future<Map<String, dynamic>>? future;
  final String? loadedFor;
  final List<Map<String, dynamic>> Function(Map<String, dynamic>) retentionRows;
  @override
  Widget build(BuildContext context) {
    if (future == null) return const Center(child: Text('Select an entity to view detail.'));
    return FutureBuilder<Map<String, dynamic>>(
      key: ValueKey('assurance-${kind.name}-$loadedFor'),
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError) return Center(child: Text('Unable to load detail: ${snapshot.error}'));
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
  Widget build(BuildContext context) => _DataCard(columns: const ['Status', 'Rule', 'Category', 'Document type', 'Matched evidence', 'Matched filename'], rows: rows.map((row) => ['${row['status'] ?? '-'}', '${row['rule_key'] ?? '-'}', '${row['category'] ?? '-'}', '${row['document_type'] ?? '-'}', '${row['matched_evidence_object_id'] ?? '-'}', '${row['matched_filename'] ?? '-'}']).toList());
}

class _ExtractionTable extends StatelessWidget {
  const _ExtractionTable({required this.rows});
  final List<Map<String, dynamic>> rows;
  @override
  Widget build(BuildContext context) => _DataCard(columns: const ['Filename', 'Method', 'Confidence', 'Characters', 'Text preview'], rows: rows.map((row) => ['${row['filename'] ?? row['object_id'] ?? '-'}', '${row['extraction_method'] ?? '-'}', '${((row['extraction_confidence'] as num?)?.toDouble() ?? 0) * 100}%', '${row['character_count'] ?? '-'}', _preview('${row['extracted_text'] ?? ''}')]).toList());
}

class _RetentionTable extends StatelessWidget {
  const _RetentionTable({required this.rows});
  final List<Map<String, dynamic>> rows;
  @override
  Widget build(BuildContext context) => _DataCard(columns: const ['Filename', 'Category', 'Document type', 'Retention class', 'Retention until', 'Legal hold', 'Deletion eligible'], rows: rows.map((row) => ['${row['filename'] ?? '-'}', '${row['category'] ?? '-'}', '${row['document_type'] ?? '-'}', '${row['retention_class'] ?? '-'}', '${row['retention_until'] ?? '-'}', '${row['legal_hold_status'] ?? 'none'}', row['deletion_eligible'] == true ? 'Yes' : 'No']).toList());
}

class _IntegrityTable extends StatelessWidget {
  const _IntegrityTable({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context) {
    final payloads = (data['payload_results'] as List<dynamic>? ?? data['payloads'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
    final failed = payloads.where((row) => row['status'] != 'valid' && row['valid'] != true).toList();
    final rows = failed.isEmpty ? payloads : failed;
    return _DataCard(columns: const ['Payload', 'Filename', 'Status', 'Expected SHA-256', 'Actual SHA-256'], rows: rows.map((row) => ['${row['hdu_name'] ?? row['payload_hdu'] ?? '-'}', '${row['filename'] ?? '-'}', '${row['status'] ?? row['valid'] ?? '-'}', '${row['expected_sha256'] ?? row['sha256'] ?? '-'}', '${row['actual_sha256'] ?? '-'}']).toList());
  }
}

class _DataCard extends StatelessWidget {
  const _DataCard({required this.columns, required this.rows});
  final List<String> columns;
  final List<List<String>> rows;
  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) return const Center(child: Text('No detail rows available.'));
    return Card(child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: SingleChildScrollView(child: DataTable(columns: columns.map((column) => DataColumn(label: Text(column))).toList(), rows: rows.map((row) => DataRow(cells: row.map((cell) => DataCell(SizedBox(width: cell.length > 80 ? 360 : null, child: Text(cell, overflow: TextOverflow.ellipsis, maxLines: 2)))).toList())).toList()))));
  }
}

String _preview(String text) => text.length <= 280 ? text : '${text.substring(0, 280)}...';
