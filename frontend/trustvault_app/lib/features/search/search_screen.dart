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
  final TextEditingController _queryController = TextEditingController(text: 'passport');
  final TextEditingController _entityController = TextEditingController();

  Future<Map<String, dynamic>>? _future;
  bool _directFits = false;
  bool _entityManuallyEdited = false;

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

    final Future<Map<String, dynamic>> nextFuture = _directFits && entity.isNotEmpty
        ? _apiClient.searchEntityFits(entity, query)
        : _apiClient.searchFitsIndex(query: query, entityExternalId: entity.isEmpty ? null : entity);

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
            TextButton.icon(
              onPressed: () => _open(_apiClient.evidenceFileUrl(objectId)),
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open'),
            ),
            TextButton.icon(
              onPressed: () => _open(_apiClient.evidenceDownloadUrl(objectId)),
              icon: const Icon(Icons.download),
              label: const Text('Download'),
            ),
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
          const Text('Search all customers through the rebuilt index, or search one selected customer directly inside its FITS archive.'),
          const SizedBox(height: 16),
          CustomerSelectorCard(
            subtitle: 'Used only when direct FITS search is enabled, or when a customer external ID is supplied below.',
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
                          decoration: const InputDecoration(labelText: 'Search query', border: OutlineInputBorder()),
                          onSubmitted: (_) => _search(),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: _entityController,
                          decoration: const InputDecoration(
                            labelText: 'Optional customer external ID',
                            border: OutlineInputBorder(),
                          ),
                          onChanged: (_) => _entityManuallyEdited = true,
                          onSubmitted: (_) => _search(),
                        ),
                      ),
                      const SizedBox(width: 12),
                      FilledButton.icon(onPressed: _search, icon: const Icon(Icons.search), label: const Text('Search')),
                    ],
                  ),
                  const SizedBox(height: 12),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Direct FITS search for selected customer'),
                    subtitle: const Text('Off: archive/index search. On: read the selected customer FITS file directly.'),
                    value: _directFits,
                    onChanged: (value) => setState(() => _directFits = value),
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
                      final results = (response['results'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();
                      if (results.isEmpty) return Center(child: Text('No results for "${response['query'] ?? _queryController.text}".'));
                      return ListView.separated(
                        itemCount: results.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final result = results[index] as Map<String, dynamic>;
                          return Card(
                            child: ListTile(
                              leading: const Icon(Icons.article_outlined),
                              title: Text('${result['filename'] ?? result['entity_display_name'] ?? 'Evidence'}'),
                              subtitle: Text(
                                'Customer: ${result['entity_external_id']}\n'
                                'Object: ${result['object_type']} from ${result['source_system']}\n'
                                'HDU: ${result['hdu_name'] ?? '-'}\n'
                                '${result['snippet'] ?? result['storage_uri'] ?? ''}',
                              ),
                              trailing: TextButton.icon(
                                onPressed: result['evidence_object_id'] == null ? null : () => _showPreview(result),
                                icon: const Icon(Icons.visibility_outlined),
                                label: const Text('Preview'),
                              ),
                            ),
                          );
                        },
                      );
                    },
                  ),
          ),
        ],
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
      return InteractiveViewer(
        child: Center(child: Image.network(apiClient.evidenceFileUrl(objectId), fit: BoxFit.contain)),
      );
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
            FilledButton.icon(
              onPressed: () => launchUrl(Uri.parse(apiClient.evidenceFileUrl(objectId)), webOnlyWindowName: '_blank'),
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open PDF'),
            ),
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
