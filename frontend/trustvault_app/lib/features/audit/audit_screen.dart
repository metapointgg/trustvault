import 'dart:convert';
import 'dart:html' as html;

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class AuditScreen extends StatefulWidget {
  const AuditScreen({super.key});

  @override
  State<AuditScreen> createState() => _AuditScreenState();
}

class _AuditScreenState extends State<AuditScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _filterController = TextEditingController();
  late Future<List<dynamic>> _future;
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getAuditEvents();
    _filterController.addListener(() => setState(() => _filter = _filterController.text.trim().toLowerCase()));
  }

  @override
  void dispose() {
    _filterController.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _filtered(List<dynamic> events) {
    final rows = events.cast<Map<String, dynamic>>();
    if (_filter.isEmpty) return rows;
    return rows.where((event) => jsonEncode(event).toLowerCase().contains(_filter)).toList();
  }

  void _exportCsv(List<Map<String, dynamic>> rows) {
    final columns = <String>['created_at', 'event_type', 'status', 'actor_user_id', 'entity_id', 'object_id', 'correlation_id'];
    String escape(Object? value) => '"${'$value'.replaceAll('"', '""')}"';
    final csv = StringBuffer()..writeln(columns.map(escape).join(','));
    for (final row in rows) {
      csv.writeln(columns.map((column) => escape(row[column] ?? '')).join(','));
    }
    final blob = html.Blob(<dynamic>[csv.toString()], 'text/csv');
    final url = html.Url.createObjectUrlFromBlob(blob);
    html.AnchorElement(href: url)
      ..download = 'trustvault-audit-log.csv'
      ..style.display = 'none'
      ..click();
    html.Url.revokeObjectUrl(url);
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
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: SelectableText(const JsonEncoder.withIndent('  ').convert(event), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
            ),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
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
                    Text('Audit log', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text('Search, review and export operational events recorded by TrustVault.'),
                  ],
                ),
              ),
              OutlinedButton.icon(onPressed: () => setState(() => _future = _apiClient.getAuditEvents()), icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _filterController,
            decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search by time, task, user, entity, object or status'),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError) return Center(child: Text('Unable to load audit events: ${snapshot.error}'));
                final events = _filtered(snapshot.data ?? <dynamic>[]);
                if (events.isEmpty) return const Center(child: Text('No matching audit events.'));
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(spacing: 8, runSpacing: 8, children: [
                      Chip(label: Text('Rows: ${events.length}')),
                      OutlinedButton.icon(onPressed: () => _exportCsv(events), icon: const Icon(Icons.download), label: const Text('Export CSV')),
                    ]),
                    const SizedBox(height: 12),
                    Expanded(
                      child: Card(
                        child: SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: SingleChildScrollView(
                            child: DataTable(
                              columns: const [
                                DataColumn(label: Text('Time')),
                                DataColumn(label: Text('Task / event')),
                                DataColumn(label: Text('Status')),
                                DataColumn(label: Text('User')),
                                DataColumn(label: Text('Entity')),
                                DataColumn(label: Text('Object')),
                                DataColumn(label: Text('Correlation')),
                                DataColumn(label: Text('Actions')),
                              ],
                              rows: events.map((event) {
                                return DataRow(cells: [
                                  DataCell(Text('${event['created_at'] ?? '-'}')),
                                  DataCell(SizedBox(width: 260, child: Text('${event['event_type'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                  DataCell(Text('${event['status'] ?? '-'}')),
                                  DataCell(SizedBox(width: 180, child: Text('${event['actor_user_id'] ?? event['user_id'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                  DataCell(SizedBox(width: 180, child: Text('${event['entity_id'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                  DataCell(SizedBox(width: 180, child: Text('${event['object_id'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                  DataCell(SizedBox(width: 240, child: Text('${event['correlation_id'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                  DataCell(TextButton.icon(onPressed: () => _showEvent(event), icon: const Icon(Icons.visibility_outlined), label: const Text('View'))),
                                ]);
                              }).toList(),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
