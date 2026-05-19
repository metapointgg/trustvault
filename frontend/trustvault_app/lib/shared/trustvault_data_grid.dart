import 'dart:convert';
import 'dart:html' as html;

import 'package:flutter/material.dart';

class TrustVaultDataGridColumn {
  const TrustVaultDataGridColumn({
    required this.key,
    required this.label,
    this.width,
    this.visibleByDefault = true,
    this.sortable = true,
    this.cellBuilder,
    this.valueBuilder,
  });

  final String key;
  final String label;
  final double? width;
  final bool visibleByDefault;
  final bool sortable;
  final Widget Function(Map<String, dynamic> row)? cellBuilder;
  final Object? Function(Map<String, dynamic> row)? valueBuilder;

  Object? value(Map<String, dynamic> row) {
    if (valueBuilder != null) return valueBuilder!(row);
    return row[key];
  }
}

class TrustVaultDataGrid extends StatefulWidget {
  const TrustVaultDataGrid({
    super.key,
    required this.title,
    required this.rows,
    required this.columns,
    this.subtitle,
    this.initialSortColumnKey,
    this.initialSortAscending = true,
    this.onRowTap,
    this.exportFilename = 'trustvault-grid.csv',
    this.emptyText = 'No rows available.',
    this.height = 420,
    this.dense = false,
  });

  final String title;
  final String? subtitle;
  final List<Map<String, dynamic>> rows;
  final List<TrustVaultDataGridColumn> columns;
  final String? initialSortColumnKey;
  final bool initialSortAscending;
  final ValueChanged<Map<String, dynamic>>? onRowTap;
  final String exportFilename;
  final String emptyText;
  final double height;
  final bool dense;

  @override
  State<TrustVaultDataGrid> createState() => _TrustVaultDataGridState();
}

class _TrustVaultDataGridState extends State<TrustVaultDataGrid> {
  final TextEditingController _searchController = TextEditingController();
  late Set<String> _visibleColumnKeys;
  String _search = '';
  String? _sortColumnKey;
  bool _sortAscending = true;

  @override
  void initState() {
    super.initState();
    _visibleColumnKeys = widget.columns.where((column) => column.visibleByDefault).map((column) => column.key).toSet();
    _sortColumnKey = widget.initialSortColumnKey;
    _sortAscending = widget.initialSortAscending;
    _searchController.addListener(() => setState(() => _search = _searchController.text.trim().toLowerCase()));
  }

  @override
  void didUpdateWidget(covariant TrustVaultDataGrid oldWidget) {
    super.didUpdateWidget(oldWidget);
    final validKeys = widget.columns.map((column) => column.key).toSet();
    _visibleColumnKeys = _visibleColumnKeys.intersection(validKeys);
    if (_visibleColumnKeys.isEmpty) {
      _visibleColumnKeys = widget.columns.where((column) => column.visibleByDefault).map((column) => column.key).toSet();
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<TrustVaultDataGridColumn> get _visibleColumns => widget.columns.where((column) => _visibleColumnKeys.contains(column.key)).toList();

  TrustVaultDataGridColumn? _columnByKey(String key) {
    for (final column in widget.columns) {
      if (column.key == key) return column;
    }
    return null;
  }

  List<Map<String, dynamic>> get _filteredRows {
    final rows = widget.rows.where((row) {
      if (_search.isEmpty) return true;
      final haystack = widget.columns.map((column) => '${column.value(row) ?? ''}').join(' ').toLowerCase();
      return haystack.contains(_search);
    }).toList();
    final sortKey = _sortColumnKey;
    if (sortKey == null) return rows;
    final sortColumn = _columnByKey(sortKey);
    if (sortColumn == null) return rows;
    rows.sort((a, b) {
      final comparison = _compareValues(sortColumn.value(a), sortColumn.value(b));
      return _sortAscending ? comparison : -comparison;
    });
    return rows;
  }

  int _compareValues(Object? a, Object? b) {
    if (a == null && b == null) return 0;
    if (a == null) return -1;
    if (b == null) return 1;
    if (a is num && b is num) return a.compareTo(b);
    final aNumber = num.tryParse('$a');
    final bNumber = num.tryParse('$b');
    if (aNumber != null && bNumber != null) return aNumber.compareTo(bNumber);
    return '$a'.toLowerCase().compareTo('$b'.toLowerCase());
  }

  void _sort(TrustVaultDataGridColumn column) {
    if (!column.sortable) return;
    setState(() {
      if (_sortColumnKey == column.key) {
        _sortAscending = !_sortAscending;
      } else {
        _sortColumnKey = column.key;
        _sortAscending = true;
      }
    });
  }

  void _exportCsv() {
    final rows = _filteredRows;
    final columns = _visibleColumns;
    String escape(Object? value) => '"${'$value'.replaceAll('"', '""').replaceAll('\n', ' ').replaceAll('\r', ' ')}"';
    final buffer = StringBuffer()..writeln(columns.map((column) => escape(column.label)).join(','));
    for (final row in rows) {
      buffer.writeln(columns.map((column) => escape(column.value(row) ?? '')).join(','));
    }
    final blob = html.Blob(<dynamic>[utf8.encode(buffer.toString())], 'text/csv;charset=utf-8');
    final url = html.Url.createObjectUrlFromBlob(blob);
    html.AnchorElement(href: url)
      ..download = widget.exportFilename
      ..style.display = 'none'
      ..click();
    html.Url.revokeObjectUrl(url);
  }

  void _showColumnPicker() {
    showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Show / hide columns'),
          content: SizedBox(
            width: 420,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: widget.columns.map((column) {
                  return CheckboxListTile(
                    value: _visibleColumnKeys.contains(column.key),
                    title: Text(column.label),
                    controlAffinity: ListTileControlAffinity.leading,
                    onChanged: (value) {
                      setDialogState(() {
                        if (value == true) {
                          _visibleColumnKeys.add(column.key);
                        } else if (_visibleColumnKeys.length > 1) {
                          _visibleColumnKeys.remove(column.key);
                        }
                      });
                      setState(() {});
                    },
                  );
                }).toList(),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                setDialogState(() => _visibleColumnKeys = widget.columns.map((column) => column.key).toSet());
                setState(() {});
              },
              child: const Text('Show all'),
            ),
            TextButton(
              onPressed: () {
                setDialogState(() => _visibleColumnKeys = widget.columns.where((column) => column.visibleByDefault).map((column) => column.key).toSet());
                setState(() {});
              },
              child: const Text('Reset'),
            ),
            FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Done')),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final rows = _filteredRows;
    final visibleColumns = _visibleColumns;
    final sortColumnIndex = visibleColumns.indexWhere((column) => column.key == _sortColumnKey);
    final table = rows.isEmpty
        ? Center(child: Padding(padding: const EdgeInsets.all(32), child: Text(widget.emptyText)))
        : SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SingleChildScrollView(
              child: DataTable(
                showCheckboxColumn: false,
                dataRowMinHeight: widget.dense ? 36 : null,
                dataRowMaxHeight: widget.dense ? 54 : null,
                headingRowHeight: widget.dense ? 44 : null,
                sortColumnIndex: sortColumnIndex >= 0 ? sortColumnIndex : null,
                sortAscending: _sortAscending,
                columns: visibleColumns.map((column) {
                  return DataColumn(label: Text(column.label), onSort: column.sortable ? (_, __) => _sort(column) : null);
                }).toList(),
                rows: rows.map((row) {
                  final cells = visibleColumns.map((column) {
                    final content = column.cellBuilder?.call(row) ?? Text('${column.value(row) ?? '-'}', overflow: TextOverflow.ellipsis, maxLines: 2);
                    return DataCell(SizedBox(width: column.width, child: content));
                  }).toList();
                  return DataRow(onSelectChanged: widget.onRowTap == null ? null : (_) => widget.onRowTap!(row), cells: cells);
                }).toList(),
              ),
            ),
          );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(widget.title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                      if (widget.subtitle != null) ...[
                        const SizedBox(height: 4),
                        Text(widget.subtitle!),
                      ],
                    ],
                  ),
                ),
                Chip(label: Text('${rows.length} / ${widget.rows.length} rows')),
                const SizedBox(width: 8),
                OutlinedButton.icon(onPressed: _showColumnPicker, icon: const Icon(Icons.view_column_outlined), label: const Text('Columns')),
                const SizedBox(width: 8),
                OutlinedButton.icon(onPressed: rows.isEmpty ? null : _exportCsv, icon: const Icon(Icons.download_outlined), label: const Text('Export CSV')),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _searchController,
              decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search this grid'),
            ),
            const SizedBox(height: 12),
            SizedBox(height: widget.height, child: Scrollbar(thumbVisibility: true, child: table)),
          ],
        ),
      ),
    );
  }
}
