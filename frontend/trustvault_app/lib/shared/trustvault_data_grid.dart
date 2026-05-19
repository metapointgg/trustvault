import 'dart:convert';
import 'dart:html' as html;

import 'package:flutter/material.dart';
import 'package:pluto_grid/pluto_grid.dart';

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
    this.isLoading = false,
    this.loadingText = 'Loading rows...',
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
  final bool isLoading;
  final String loadingText;

  @override
  State<TrustVaultDataGrid> createState() => _TrustVaultDataGridState();
}

class _TrustVaultDataGridState extends State<TrustVaultDataGrid> {
  final TextEditingController _searchController = TextEditingController();
  PlutoGridStateManager? _stateManager;
  late Set<String> _visibleColumnKeys;
  String _search = '';

  @override
  void initState() {
    super.initState();
    _visibleColumnKeys = widget.columns
        .where((column) => column.visibleByDefault)
        .map((column) => column.key)
        .toSet();
    _searchController.addListener(() {
      setState(() => _search = _searchController.text.trim().toLowerCase());
    });
  }

  @override
  void didUpdateWidget(covariant TrustVaultDataGrid oldWidget) {
    super.didUpdateWidget(oldWidget);
    final validKeys = widget.columns.map((column) => column.key).toSet();
    _visibleColumnKeys = _visibleColumnKeys.intersection(validKeys);
    if (_visibleColumnKeys.isEmpty) {
      _visibleColumnKeys = widget.columns
          .where((column) => column.visibleByDefault)
          .map((column) => column.key)
          .toSet();
    }
    WidgetsBinding.instance
        .addPostFrameCallback((_) => _syncColumnVisibility());
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<TrustVaultDataGridColumn> get _visibleColumns => widget.columns
      .where((column) => _visibleColumnKeys.contains(column.key))
      .toList();

  List<Map<String, dynamic>> get _filteredRows {
    if (_search.isEmpty) return widget.rows;
    return widget.rows.where((row) {
      final haystack = widget.columns
          .map((column) => '${column.value(row) ?? ''}')
          .join(' ')
          .toLowerCase();
      return haystack.contains(_search);
    }).toList();
  }

  List<PlutoColumn> _plutoColumns() {
    return widget.columns.map((column) {
      return PlutoColumn(
        title: column.label,
        field: column.key,
        type: PlutoColumnType.text(),
        width: column.width ?? 160,
        minWidth: 70,
        enableSorting: column.sortable,
        enableContextMenu: true,
        enableDropToResize: true,
        hide: !_visibleColumnKeys.contains(column.key),
        renderer: (rendererContext) {
          final raw = rendererContext.row.cells['_raw']?.value;
          final sourceRow =
              raw is Map<String, dynamic> ? raw : <String, dynamic>{};
          if (column.cellBuilder != null) return column.cellBuilder!(sourceRow);
          final value = rendererContext.cell.value;
          return Text('$value',
              overflow: TextOverflow.ellipsis, maxLines: widget.dense ? 1 : 2);
        },
      );
    }).toList();
  }

  List<PlutoRow> _plutoRows() {
    final rows = _filteredRows;
    return rows.map((row) {
      final cells = <String, PlutoCell>{'_raw': PlutoCell(value: row)};
      for (final column in widget.columns) {
        cells[column.key] = PlutoCell(value: column.value(row) ?? '');
      }
      return PlutoRow(cells: cells);
    }).toList();
  }

  void _syncColumnVisibility() {
    final manager = _stateManager;
    if (manager == null) return;
    for (final column in manager.columns) {
      if (column.field == '_raw') continue;
      final shouldHide = !_visibleColumnKeys.contains(column.field);
      if (column.hide != shouldHide) {
        manager.hideColumn(column, shouldHide);
      }
    }
  }

  void _exportCsv() {
    final rows = _filteredRows;
    final columns = _visibleColumns;
    String escape(Object? value) =>
        '"${'$value'.replaceAll('"', '""').replaceAll('\n', ' ').replaceAll('\r', ' ')}"';
    final buffer = StringBuffer()
      ..writeln(columns.map((column) => escape(column.label)).join(','));
    for (final row in rows) {
      buffer.writeln(
          columns.map((column) => escape(column.value(row) ?? '')).join(','));
    }
    final blob = html.Blob(
        <dynamic>[utf8.encode(buffer.toString())], 'text/csv;charset=utf-8');
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
                      WidgetsBinding.instance
                          .addPostFrameCallback((_) => _syncColumnVisibility());
                    },
                  );
                }).toList(),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                setDialogState(() => _visibleColumnKeys =
                    widget.columns.map((column) => column.key).toSet());
                setState(() {});
                WidgetsBinding.instance
                    .addPostFrameCallback((_) => _syncColumnVisibility());
              },
              child: const Text('Show all'),
            ),
            TextButton(
              onPressed: () {
                setDialogState(() => _visibleColumnKeys = widget.columns
                    .where((column) => column.visibleByDefault)
                    .map((column) => column.key)
                    .toSet());
                setState(() {});
                WidgetsBinding.instance
                    .addPostFrameCallback((_) => _syncColumnVisibility());
              },
              child: const Text('Reset'),
            ),
            FilledButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Done')),
          ],
        ),
      ),
    );
  }

  void _onLoaded(PlutoGridOnLoadedEvent event) {
    _stateManager = event.stateManager;
    _stateManager!.setShowColumnFilter(false);
    if (widget.initialSortColumnKey != null) {
      final matching = _stateManager!.columns
          .where((column) => column.field == widget.initialSortColumnKey)
          .toList();
      if (matching.isNotEmpty) {
        _stateManager!.sortAscending(matching.first, notify: false);
        if (!widget.initialSortAscending) {
          _stateManager!.sortDescending(matching.first, notify: false);
        }
      }
    }
  }

  void _onSelected(PlutoGridOnSelectedEvent event) {
    if (widget.onRowTap == null) return;
    final raw = event.row?.cells['_raw']?.value;
    if (raw is Map<String, dynamic>) widget.onRowTap!(raw);
  }

  @override
  Widget build(BuildContext context) {
    final rows = _filteredRows;
    final grid = rows.isEmpty && !widget.isLoading
        ? Center(
            child: Padding(
                padding: const EdgeInsets.all(32),
                child: Text(widget.emptyText)))
        : PlutoGrid(
            key: ValueKey(
                '${widget.title}-${widget.rows.length}-$_search-${_visibleColumnKeys.join('|')}'),
            columns: _plutoColumns(),
            rows: _plutoRows(),
            mode: widget.onRowTap == null
                ? PlutoGridMode.normal
                : PlutoGridMode.selectWithOneTap,
            onLoaded: _onLoaded,
            onSelected: _onSelected,
            configuration: PlutoGridConfiguration(
              columnSize: const PlutoGridColumnSizeConfig(
                  autoSizeMode: PlutoAutoSizeMode.none),
              columnFilter: PlutoGridColumnFilterConfig(
                filters: const [
                  PlutoFilterTypeEquals(),
                  PlutoFilterTypeStartsWith(),
                  PlutoFilterTypeEndsWith(),
                  PlutoFilterTypeGreaterThan(),
                  PlutoFilterTypeGreaterThanOrEqualTo(),
                  PlutoFilterTypeLessThan(),
                  PlutoFilterTypeLessThanOrEqualTo(),
                ],
                resolveDefaultColumnFilter: (column, resolver) =>
                    resolver<PlutoFilterTypeEquals>(),
              ),
              style: PlutoGridStyleConfig(
                rowHeight: widget.dense ? 34 : 42,
                columnHeight: widget.dense ? 38 : 44,
                activatedColor: Theme.of(context).colorScheme.primaryContainer,
                gridBorderColor: Theme.of(context).colorScheme.outlineVariant,
                borderColor: Theme.of(context).colorScheme.outlineVariant,
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
                      Text(widget.title,
                          style: Theme.of(context)
                              .textTheme
                              .titleLarge
                              ?.copyWith(fontWeight: FontWeight.w700)),
                      if (widget.subtitle != null) ...[
                        const SizedBox(height: 4),
                        Text(widget.subtitle!),
                      ],
                    ],
                  ),
                ),
                Chip(
                    label: Text('${rows.length} / ${widget.rows.length} rows')),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                    onPressed: _showColumnPicker,
                    icon: const Icon(Icons.view_column_outlined),
                    label: const Text('Columns')),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                    onPressed: rows.isEmpty ? null : _exportCsv,
                    icon: const Icon(Icons.download_outlined),
                    label: const Text('Export CSV')),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.search),
                  labelText: 'Search this grid'),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: widget.height,
              child: Stack(
                children: [
                  Positioned.fill(
                      child: Opacity(
                          opacity: widget.isLoading ? 0.55 : 1, child: grid)),
                  if (widget.isLoading)
                    Positioned.fill(
                      child: ColoredBox(
                        color: Theme.of(context)
                            .colorScheme
                            .surface
                            .withValues(alpha: 0.35),
                        child: Center(
                          child: Card(
                            child: Padding(
                              padding: const EdgeInsets.all(18),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const SizedBox(
                                      width: 22,
                                      height: 22,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2)),
                                  const SizedBox(width: 12),
                                  Text(widget.loadingText),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
