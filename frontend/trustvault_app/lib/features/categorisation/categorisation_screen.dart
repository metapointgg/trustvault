import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class CategorisationScreen extends StatefulWidget {
  const CategorisationScreen({super.key});

  @override
  State<CategorisationScreen> createState() => _CategorisationScreenState();
}

class _CategorisationScreenState extends State<CategorisationScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<void> _loadFuture;
  List<Map<String, dynamic>> _rows = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _documentTypes = <Map<String, dynamic>>[];
  final Set<String> _selectedIds = <String>{};
  String? _message;
  String? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadFuture = _load();
  }

  Future<void> _load() async {
    final responses = await Future.wait<dynamic>([
      _apiClient.getUncategorisedEvidence(),
      _apiClient.getDocumentClassificationSettings(),
    ]);
    final evidence = (responses[0] as List<dynamic>).cast<dynamic>();
    final settings = responses[1] as Map<String, dynamic>;
    setState(() {
      _rows = evidence.map((item) => (item as Map<String, dynamic>)).toList();
      _documentTypes = ((settings['document_types'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>()).toList();
      _selectedIds.removeWhere((id) => !_rows.any((row) => row['evidence_object_id'] == id));
    });
  }

  Future<void> _refresh() async {
    setState(() {
      _message = null;
      _error = null;
      _loadFuture = _load();
    });
  }

  Future<void> _showSetDialog() async {
    if (_selectedIds.isEmpty) return;
    String? selectedDocumentType = _documentTypes.isNotEmpty ? '${_documentTypes.first['document_type']}' : null;
    final result = await showDialog<String>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) {
          final selectedMapping = _documentTypes.where((item) => item['document_type'] == selectedDocumentType).cast<Map<String, dynamic>?>().firstOrNull;
          return AlertDialog(
            title: const Text('Set document type'),
            content: SizedBox(
              width: 520,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Update ${_selectedIds.length} selected evidence item(s).'),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<String>(
                    value: selectedDocumentType,
                    decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Document type'),
                    items: _documentTypes
                        .map((item) => DropdownMenuItem<String>(
                              value: '${item['document_type']}',
                              child: Text('${item['document_type']}'),
                            ))
                        .toList(),
                    onChanged: (value) => setDialogState(() => selectedDocumentType = value),
                  ),
                  const SizedBox(height: 12),
                  if (selectedMapping != null)
                    Text('Category will be set automatically to: ${selectedMapping['category']}', style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  const Text('Category is controlled in Settings and is not manually set here.'),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
              FilledButton(onPressed: selectedDocumentType == null ? null : () => Navigator.of(context).pop(selectedDocumentType), child: const Text('Set')),
            ],
          );
        },
      ),
    );

    if (result == null || result.isEmpty) return;
    await _setDocumentType(result);
  }

  Future<void> _setDocumentType(String documentType) async {
    setState(() {
      _saving = true;
      _message = null;
      _error = null;
    });
    try {
      final response = await _apiClient.updateEvidenceClassification(evidenceObjectIds: _selectedIds.toList(), documentType: documentType);
      setState(() {
        _message = 'Updated ${response['updated_count'] ?? _selectedIds.length} evidence item(s) to $documentType.';
        _selectedIds.clear();
        _saving = false;
        _loadFuture = _load();
      });
    } catch (error) {
      setState(() {
        _error = '$error';
        _saving = false;
      });
    }
  }

  void _toggleRow(String id, bool selected) {
    setState(() {
      if (selected) {
        _selectedIds.add(id);
      } else {
        _selectedIds.remove(id);
      }
    });
  }

  void _toggleAll(bool selected) {
    setState(() {
      if (selected) {
        _selectedIds.addAll(_rows.map((row) => '${row['evidence_object_id']}'));
      } else {
        _selectedIds.clear();
      }
    });
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
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Categorisation', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      const Text('Review uncategorised evidence and set the Document Type. Category is derived from Settings.'),
                    ],
                  ),
                ),
                OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
                const SizedBox(width: 12),
                FilledButton.icon(
                  onPressed: _saving || _selectedIds.isEmpty ? null : _showSetDialog,
                  icon: _saving ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.edit_outlined),
                  label: Text(_selectedIds.isEmpty ? 'Select evidence' : 'Set (${_selectedIds.length})'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_message != null) _Banner(message: _message!, positive: true),
            if (_error != null) _Banner(message: _error!, positive: false),
            const SizedBox(height: 16),
            FutureBuilder<void>(
              future: _loadFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: Padding(padding: EdgeInsets.all(48), child: CircularProgressIndicator()));
                }
                if (snapshot.hasError) return _Banner(message: 'Unable to load categorisation data: ${snapshot.error}', positive: false);
                return _CategorisationTable(
                  rows: _rows,
                  selectedIds: _selectedIds,
                  onToggleRow: _toggleRow,
                  onToggleAll: _toggleAll,
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _CategorisationTable extends StatelessWidget {
  const _CategorisationTable({required this.rows, required this.selectedIds, required this.onToggleRow, required this.onToggleAll});

  final List<Map<String, dynamic>> rows;
  final Set<String> selectedIds;
  final void Function(String id, bool selected) onToggleRow;
  final void Function(bool selected) onToggleAll;

  @override
  Widget build(BuildContext context) {
    final allSelected = rows.isNotEmpty && selectedIds.length == rows.length;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text('Uncategorised evidence', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700))),
                Chip(label: Text('${rows.length} rows')),
              ],
            ),
            const SizedBox(height: 12),
            if (rows.isEmpty)
              const Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No uncategorised evidence found.')))
            else
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  columns: [
                    DataColumn(label: Checkbox(value: allSelected, onChanged: (value) => onToggleAll(value == true))),
                    const DataColumn(label: Text('Entity')),
                    const DataColumn(label: Text('Filename')),
                    const DataColumn(label: Text('Current document type')),
                    const DataColumn(label: Text('Current category')),
                    const DataColumn(label: Text('Status')),
                    const DataColumn(label: Text('Confidence')),
                    const DataColumn(label: Text('Source')),
                  ],
                  rows: rows.map((row) {
                    final id = '${row['evidence_object_id']}';
                    final selected = selectedIds.contains(id);
                    return DataRow(
                      selected: selected,
                      cells: [
                        DataCell(Checkbox(value: selected, onChanged: (value) => onToggleRow(id, value == true))),
                        DataCell(Text('${row['entity_external_id'] ?? ''}')),
                        DataCell(SizedBox(width: 260, child: Text('${row['filename'] ?? row['source_path'] ?? ''}', overflow: TextOverflow.ellipsis))),
                        DataCell(Text('${row['document_type'] ?? ''}')),
                        DataCell(Text('${row['category'] ?? ''}')),
                        DataCell(Text('${row['classification_status'] ?? ''}')),
                        DataCell(Text('${row['classification_confidence'] ?? ''}')),
                        DataCell(Text('${row['classification_source'] ?? ''}')),
                      ],
                    );
                  }).toList(),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.message, required this.positive});

  final String message;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: positive ? scheme.primaryContainer : scheme.errorContainer, borderRadius: BorderRadius.circular(12)),
      child: Text(message, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
    );
  }
}
