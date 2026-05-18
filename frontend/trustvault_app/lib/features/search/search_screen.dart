import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/customer_selector_card.dart';
import '../../shared/selected_customer.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _queryController = TextEditingController(text: 'Show me all onboarding documentation for high risk clients in Guernsey.');
  final TextEditingController _entityController = TextEditingController();

  Future<Map<String, dynamic>>? _future;
  bool _directFits = false;
  bool _entityManuallyEdited = false;
  bool _useNaturalLanguage = true;
  bool _includeAiSummary = false;
  String _aiMode = 'auto';
  int _limit = 50;

  @override
  void initState() {
    super.initState();
    _syncEntityFromSelectedCustomer();
    SelectedCustomerController.selected.addListener(_handleSelectedCustomerChanged);
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_handleSelectedCustomerChanged);
    _queryController.dispose();
    _entityController.dispose();
    super.dispose();
  }

  void _handleSelectedCustomerChanged() {
    if (_entityManuallyEdited) return;
    _syncEntityFromSelectedCustomer();
  }

  void _syncEntityFromSelectedCustomer() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId != null && externalId.isNotEmpty && _entityController.text != externalId) {
      _entityController.text = externalId;
    }
  }

  void _search() {
    final query = _queryController.text.trim();
    final entity = _entityController.text.trim();
    if (query.isEmpty) return;

    final Future<Map<String, dynamic>> nextFuture;
    if (_useNaturalLanguage) {
      nextFuture = _apiClient.executeQuery(
        query: query,
        entityExternalId: entity.isEmpty ? null : entity,
        mode: _aiMode,
        limit: _limit,
        includeAiSummary: _includeAiSummary,
      );
    } else {
      nextFuture = _directFits && entity.isNotEmpty
          ? _apiClient.searchEntityFits(entity, query)
          : _apiClient.searchFitsIndex(query: query, entityExternalId: entity.isEmpty ? null : entity);
    }

    setState(() {
      _future = nextFuture;
    });
  }

  Future<void> _showPreview(Map<String, dynamic> result) async {
    final objectId = '${result['evidence_object_id']}';
    final preview = await _apiClient.getEvidencePreview(objectId);
    if (!mounted) return;

    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text('${preview['filename'] ?? result['filename'] ?? result['entity_display_name'] ?? 'Evidence preview'}'),
          content: SizedBox(
            width: 900,
            height: 680,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    Chip(label: Text('Kind: ${preview['preview_kind'] ?? '-'}')),
                    Chip(label: Text('Type: ${preview['content_type'] ?? '-'}')),
                    Chip(label: Text('Size: ${preview['size_bytes'] ?? '-'} bytes')),
                    Chip(label: Text('SHA-256: ${preview['sha256'] ?? '-'}')),
                  ],
                ),
                const SizedBox(height: 12),
                Expanded(child: _EvidencePreviewBody(apiClient: _apiClient, preview: preview)),
              ],
            ),
          ),
          actions: [
            TextButton.icon(onPressed: () => _open(_apiClient.evidenceFileUrl(objectId)), icon: const Icon(Icons.open_in_new), label: const Text('Open')),
            TextButton.icon(onPressed: () => _open(_apiClient.evidenceDownloadUrl(objectId)), icon: const Icon(Icons.download), label: const Text('Download')),
            TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
          ],
        );
      },
    );
  }

  Future<void> _open(String url) async {
    await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Evidence search', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Ask natural-language evidence questions, optionally using AI interpretation and summaries, or run raw FITS/index searches.'),
          const SizedBox(height: 16),
          CustomerSelectorCard(
            subtitle: 'Used for selected-customer direct FITS searches and scoped natural-language questions.',
            onChanged: (_) {
              _entityManuallyEdited = false;
              _syncEntityFromSelectedCustomer();
            },
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: TextField(
                          controller: _queryController,
                          maxLines: 2,
                          decoration: const InputDecoration(labelText: 'Search query or question', border: OutlineInputBorder()),
                          onSubmitted: (_) => _search(),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: _entityController,
                          decoration: const InputDecoration(labelText: 'Optional customer external ID', border: OutlineInputBorder()),
                          onChanged: (_) => _entityManuallyEdited = true,
                          onSubmitted: (_) => _search(),
                        ),
                      ),
                      const SizedBox(width: 12),
                      FilledButton.icon(onPressed: _search, icon: const Icon(Icons.search), label: const Text('Search')),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Natural-language execution'),
                          subtitle: const Text('Uses the TrustVault interpreter; selected-customer evidence searches use direct FITS where appropriate.'),
                          value: _useNaturalLanguage,
                          onChanged: (value) => setState(() => _useNaturalLanguage = value),
                        ),
                      ),
                      const SizedBox(width: 16),
                      SizedBox(
                        width: 240,
                        child: DropdownButtonFormField<String>(
                          value: _aiMode,
                          decoration: const InputDecoration(labelText: 'Interpretation mode', border: OutlineInputBorder()),
                          items: const [
                            DropdownMenuItem(value: 'auto', child: Text('Auto')),
                            DropdownMenuItem(value: 'deterministic', child: Text('Deterministic')),
                            DropdownMenuItem(value: 'ai', child: Text('AI assisted')),
                          ],
                          onChanged: _useNaturalLanguage ? (value) => setState(() => _aiMode = value ?? 'auto') : null,
                        ),
                      ),
                      const SizedBox(width: 16),
                      SizedBox(
                        width: 150,
                        child: DropdownButtonFormField<int>(
                          value: _limit,
                          decoration: const InputDecoration(labelText: 'Limit', border: OutlineInputBorder()),
                          items: const [25, 50, 100, 250, 500].map((value) => DropdownMenuItem(value: value, child: Text('$value'))).toList(),
                          onChanged: (value) => setState(() => _limit = value ?? 50),
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      Expanded(
                        child: SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Generate AI evidence summary'),
                          subtitle: const Text('Summarises retrieved rows only. FITS payloads, manifest metadata and hashes remain the source of truth.'),
                          value: _includeAiSummary,
                          onChanged: _useNaturalLanguage ? (value) => setState(() => _includeAiSummary = value) : null,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Raw direct FITS search'),
                          subtitle: const Text('Only used when natural-language execution is off and a customer ID is supplied.'),
                          value: _directFits,
                          onChanged: !_useNaturalLanguage ? (value) => setState(() => _directFits = value) : null,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: _future == null
                ? const Center(child: Text('Enter a query to search evidence.'))
                : FutureBuilder<Map<String, dynamic>>(
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                      if (snapshot.hasError) return Center(child: Text('Unable to search evidence: ${snapshot.error}'));
                      final response = snapshot.data ?? <String, dynamic>{};
                      return _SearchResultTable(response: response, onPreview: _showPreview);
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _SearchResultTable extends StatefulWidget {
  const _SearchResultTable({required this.response, required this.onPreview});

  final Map<String, dynamic> response;
  final Future<void> Function(Map<String, dynamic> result) onPreview;

  @override
  State<_SearchResultTable> createState() => _SearchResultTableState();
}

class _SearchResultTableState extends State<_SearchResultTable> {
  int? _selectedIndex;

  @override
  Widget build(BuildContext context) {
    final normalised = _normaliseResponse(widget.response);
    final rows = normalised.rows;
    final summary = normalised.aiSummary;
    final interpretation = normalised.interpretation;
    final structured = normalised.structuredQuery;

    if (rows.isEmpty) {
      return Center(child: Text('No results for "${normalised.query}".'));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            Chip(label: Text('Results: ${rows.length}')),
            Chip(label: Text('Source: ${normalised.executionSource}')),
            if (interpretation.isNotEmpty) Chip(label: Text('AI used: ${interpretation['ai_used'] ?? false}')),
            if (interpretation['ai_model'] != null) Chip(label: Text('Model: ${interpretation['ai_model']}')),
            if (structured['snapshot_id'] != null) Chip(label: Text('Snapshot: ${structured['snapshot_id']}')),
            if (structured['risk_rating'] != null) Chip(label: Text('Risk: ${structured['risk_rating']}')),
            if (structured['jurisdiction'] != null) Chip(label: Text('Jurisdiction: ${structured['jurisdiction']}')),
          ],
        ),
        if (summary != null) ...[
          const SizedBox(height: 12),
          _AiSummaryPanel(summary: summary),
        ],
        const SizedBox(height: 12),
        Expanded(
          child: Card(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SingleChildScrollView(
                child: DataTable(
                  showCheckboxColumn: false,
                  columns: const [
                    DataColumn(label: Text('Customer')),
                    DataColumn(label: Text('Name')),
                    DataColumn(label: Text('Filename')),
                    DataColumn(label: Text('Object type')),
                    DataColumn(label: Text('Source')),
                    DataColumn(label: Text('HDU')),
                    DataColumn(label: Text('SHA-256')),
                    DataColumn(label: Text('Snippet')),
                    DataColumn(label: Text('Actions')),
                  ],
                  rows: List.generate(rows.length, (index) {
                    final row = rows[index];
                    final selected = _selectedIndex == index;
                    return DataRow(
                      selected: selected,
                      onSelectChanged: (_) => setState(() => _selectedIndex = index),
                      cells: [
                        DataCell(Text('${row['entity_external_id'] ?? '-'}')),
                        DataCell(SizedBox(width: 220, child: Text('${row['entity_display_name'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                        DataCell(SizedBox(width: 260, child: Text('${row['filename'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                        DataCell(Text('${row['object_type'] ?? '-'}')),
                        DataCell(Text('${row['source_system'] ?? '-'}')),
                        DataCell(Text('${row['hdu_name'] ?? '-'}')),
                        DataCell(SizedBox(width: 170, child: SelectableText('${row['sha256'] ?? '-'}'))),
                        DataCell(SizedBox(width: 420, child: Text('${row['snippet'] ?? row['storage_uri'] ?? ''}', overflow: TextOverflow.ellipsis, maxLines: 2))),
                        DataCell(TextButton.icon(
                          onPressed: row['evidence_object_id'] == null ? null : () => widget.onPreview(row),
                          icon: const Icon(Icons.visibility_outlined),
                          label: const Text('Preview'),
                        )),
                      ],
                    );
                  }),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  _NormalisedSearchResponse _normaliseResponse(Map<String, dynamic> response) {
    final query = '${response['query'] ?? response['result']?['query'] ?? ''}';
    final result = response['result'] is Map<String, dynamic> ? response['result'] as Map<String, dynamic> : response;
    final rawRows = (result['results'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();
    final rows = rawRows.whereType<Map<String, dynamic>>().toList();
    return _NormalisedSearchResponse(
      query: query,
      executionSource: '${response['execution_source'] ?? result['execution_source'] ?? 'fits_index'}',
      rows: rows,
      aiSummary: response['ai_summary'] is Map<String, dynamic> ? response['ai_summary'] as Map<String, dynamic> : null,
      interpretation: response['interpretation'] is Map<String, dynamic> ? response['interpretation'] as Map<String, dynamic> : <String, dynamic>{},
      structuredQuery: response['structured_query'] is Map<String, dynamic> ? response['structured_query'] as Map<String, dynamic> : <String, dynamic>{},
    );
  }
}

class _NormalisedSearchResponse {
  const _NormalisedSearchResponse({required this.query, required this.executionSource, required this.rows, required this.aiSummary, required this.interpretation, required this.structuredQuery});

  final String query;
  final String executionSource;
  final List<Map<String, dynamic>> rows;
  final Map<String, dynamic>? aiSummary;
  final Map<String, dynamic> interpretation;
  final Map<String, dynamic> structuredQuery;
}

class _AiSummaryPanel extends StatelessWidget {
  const _AiSummaryPanel({required this.summary});

  final Map<String, dynamic> summary;

  @override
  Widget build(BuildContext context) {
    final available = summary['available'] == true;
    final text = summary['summary'] ?? summary['warning'] ?? 'No AI summary returned.';
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: available ? scheme.primaryContainer.withValues(alpha: 0.45) : scheme.errorContainer.withValues(alpha: 0.45),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.psychology_alt_outlined, color: available ? scheme.primary : scheme.error),
                const SizedBox(width: 8),
                Text('AI evidence summary', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                const Spacer(),
                if (summary['provider'] != null) Chip(label: Text('${summary['provider']}')),
                if (summary['model'] != null) Chip(label: Text('${summary['model']}')),
              ],
            ),
            const SizedBox(height: 8),
            SelectableText('$text'),
            const SizedBox(height: 8),
            Text('${summary['source_of_truth_notice'] ?? 'The preserved FITS evidence remains the source of truth.'}', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _EvidencePreviewBody extends StatelessWidget {
  const _EvidencePreviewBody({required this.apiClient, required this.preview});

  final TrustVaultApiClient apiClient;
  final Map<String, dynamic> preview;

  @override
  Widget build(BuildContext context) {
    final kind = '${preview['preview_kind'] ?? 'binary'}';
    final objectId = '${preview['evidence_object_id']}';
    if (kind == 'image') {
      return InteractiveViewer(child: Center(child: Image.network(apiClient.evidenceFileUrl(objectId), fit: BoxFit.contain)));
    }
    if (kind == 'pdf') {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.picture_as_pdf_outlined, size: 64),
            const SizedBox(height: 12),
            const Text('PDF preview opens in a new browser tab.'),
            const SizedBox(height: 12),
            FilledButton.icon(onPressed: () => launchUrl(Uri.parse(apiClient.evidenceFileUrl(objectId)), webOnlyWindowName: '_blank'), icon: const Icon(Icons.open_in_new), label: const Text('Open PDF')),
          ],
        ),
      );
    }
    final text = preview['safe_preview'] ?? preview['text_preview'];
    if (kind == 'eml' || kind == 'text') {
      return SingleChildScrollView(child: SelectableText('$text'));
    }
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.insert_drive_file_outlined, size: 64),
          const SizedBox(height: 12),
          Text('No inline preview is available for ${preview['content_type'] ?? 'this file type'}.'),
        ],
      ),
    );
  }
}
