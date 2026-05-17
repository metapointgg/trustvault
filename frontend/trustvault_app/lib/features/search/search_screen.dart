import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _queryController = TextEditingController(text: 'verified');

  Future<Map<String, dynamic>>? _future;

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  void _search() {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;
    setState(() => _future = _apiClient.searchEvidence(query));
  }

  Future<void> _showPreview(Map<String, dynamic> result) async {
    final preview = await _apiClient.getEvidencePreview('${result['evidence_object_id']}');
    if (!mounted) return;

    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text('${result['entity_display_name']}'),
          content: SizedBox(
            width: 760,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  _PreviewRow(label: 'Evidence object', value: '${preview['evidence_object_id']}'),
                  _PreviewRow(label: 'Object type', value: '${preview['object_type']}'),
                  _PreviewRow(label: 'Source system', value: '${preview['source_system']}'),
                  _PreviewRow(label: 'Storage URI', value: '${preview['storage_uri']}'),
                  _PreviewRow(label: 'SHA-256', value: '${preview['sha256']}'),
                  _PreviewRow(label: 'Size', value: '${preview['size_bytes']} bytes'),
                  const SizedBox(height: 16),
                  Text('Text preview', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: SelectableText('${preview['text_preview'] ?? 'No text preview available.'}'),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
          ],
        );
      },
    );
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
          const Text('Search stored local text evidence and metadata. This is the first lightweight search layer before PostgreSQL full-text search.'),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _queryController,
                      decoration: const InputDecoration(
                        labelText: 'Search query',
                        border: OutlineInputBorder(),
                      ),
                      onSubmitted: (_) => _search(),
                    ),
                  ),
                  const SizedBox(width: 12),
                  FilledButton.icon(
                    onPressed: _search,
                    icon: const Icon(Icons.search),
                    label: const Text('Search'),
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
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (snapshot.hasError) {
                        return Center(child: Text('Unable to search evidence: ${snapshot.error}'));
                      }

                      final response = snapshot.data ?? <String, dynamic>{};
                      final results = (response['results'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();

                      if (results.isEmpty) {
                        return Center(child: Text('No results for "${response['query'] ?? _queryController.text}".'));
                      }

                      return ListView.separated(
                        itemCount: results.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final result = results[index] as Map<String, dynamic>;
                          return Card(
                            child: ListTile(
                              leading: const Icon(Icons.manage_search_outlined),
                              title: Text('${result['entity_display_name']}'),
                              subtitle: Text(
                                'External ID: ${result['entity_external_id']}\n'
                                'Object: ${result['object_type']} from ${result['source_system']}\n'
                                'Match: ${result['match_source']}\n'
                                '${result['snippet'] ?? result['storage_uri']}',
                              ),
                              trailing: TextButton.icon(
                                onPressed: () => _showPreview(result),
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

class _PreviewRow extends StatelessWidget {
  const _PreviewRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 130, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700))),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }
}
