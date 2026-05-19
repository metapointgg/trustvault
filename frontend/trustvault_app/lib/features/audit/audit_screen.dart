import 'dart:convert';

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/trustvault_data_grid.dart';

class AuditScreen extends StatefulWidget {
  const AuditScreen({super.key});

  @override
  State<AuditScreen> createState() => _AuditScreenState();
}

class _AuditScreenState extends State<AuditScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getAuditEvents();
  }

  String _userLabel(Map<String, dynamic> event) {
    final metadata = event['metadata_json'] as Map<String, dynamic>? ?? <String, dynamic>{};
    return '${metadata['user_display_name'] ?? metadata['user_email'] ?? event['user_name'] ?? event['user_id'] ?? '-'}';
  }

  String _entityLabel(Map<String, dynamic> event) {
    final metadata = event['metadata_json'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final externalIds = metadata['entity_external_ids'];
    if (externalIds is List && externalIds.isNotEmpty) return externalIds.take(3).join(', ');
    final entityIds = event['entity_ids'];
    if (entityIds is List && entityIds.isNotEmpty) return entityIds.take(2).join(', ');
    return '-';
  }

  String _objectLabel(Map<String, dynamic> event) {
    final objectIds = event['object_ids'];
    if (objectIds is List && objectIds.isNotEmpty) return objectIds.take(2).join(', ');
    final metadata = event['metadata_json'] as Map<String, dynamic>? ?? <String, dynamic>{};
    return '${metadata['object_id'] ?? '-'}';
  }

  Map<String, dynamic> _row(Map<String, dynamic> event) {
    return <String, dynamic>{
      ...event,
      'user_label': _userLabel(event),
      'entity_label': _entityLabel(event),
      'object_label': _objectLabel(event),
      'metadata_text': jsonEncode(event['metadata_json'] ?? <String, dynamic>{}),
    };
  }

  void _showEvent(Map<String, dynamic> event) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${event['event_type'] ?? 'Audit event'}'),
        content: SizedBox(
          width: 920,
          height: 620,
          child: DecoratedBox(
            decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
            child: SingleChildScrollView(padding: const EdgeInsets.all(16), child: SelectableText(const JsonEncoder.withIndent('  ').convert(event), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace'))),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  List<TrustVaultDataGridColumn> _columns() => [
    const TrustVaultDataGridColumn(key: 'created_at', label: 'Time', width: 210),
    const TrustVaultDataGridColumn(key: 'event_type', label: 'Task / event', width: 240),
    const TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 110),
    const TrustVaultDataGridColumn(key: 'user_label', label: 'User', width: 240),
    const TrustVaultDataGridColumn(key: 'entity_label', label: 'Entity', width: 260),
    const TrustVaultDataGridColumn(key: 'object_label', label: 'Object', width: 260),
    const TrustVaultDataGridColumn(key: 'result_count', label: 'Results', width: 90),
    const TrustVaultDataGridColumn(key: 'search_source', label: 'Source', width: 160),
    const TrustVaultDataGridColumn(key: 'correlation_id', label: 'Correlation', width: 260, visibleByDefault: false),
    const TrustVaultDataGridColumn(key: 'raw_query', label: 'Raw query', width: 360, visibleByDefault: false),
    const TrustVaultDataGridColumn(key: 'metadata_text', label: 'Metadata', width: 420, visibleByDefault: false),
    TrustVaultDataGridColumn(key: 'actions', label: 'Actions', width: 80, sortable: false, valueBuilder: (_) => '', cellBuilder: (row) => TextButton.icon(onPressed: () => _showEvent(row), icon: const Icon(Icons.visibility_outlined), label: const Text('View'))),
  ];

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Audit log', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)), const SizedBox(height: 8), const Text('Search, review and export operational events recorded by TrustVault.')])),
            OutlinedButton.icon(onPressed: () => setState(() => _future = _apiClient.getAuditEvents()), icon: const Icon(Icons.refresh), label: const Text('Refresh')),
          ]),
          const SizedBox(height: 16),
          FutureBuilder<List<dynamic>>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) return const SizedBox(height: 520, child: Center(child: CircularProgressIndicator()));
              if (snapshot.hasError) return SizedBox(height: 520, child: Center(child: Text('Unable to load audit events: ${snapshot.error}')));
              final rows = (snapshot.data ?? <dynamic>[]).cast<Map<String, dynamic>>().map(_row).toList();
              return TrustVaultDataGrid(title: 'Audit events', subtitle: 'Search by time, task, user, entity, object or status. Export uses currently visible columns and filtered rows.', rows: rows, columns: _columns(), initialSortColumnKey: 'created_at', initialSortAscending: false, onRowTap: _showEvent, exportFilename: 'trustvault-audit-log.csv', emptyText: 'No matching audit events.', height: 680, dense: true);
            },
          ),
          const SizedBox(height: 32),
        ]),
      ),
    );
  }
}
