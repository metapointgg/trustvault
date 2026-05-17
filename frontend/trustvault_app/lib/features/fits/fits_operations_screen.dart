import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class FitsOperationsScreen extends StatefulWidget {
  const FitsOperationsScreen({super.key});

  @override
  State<FitsOperationsScreen> createState() => _FitsOperationsScreenState();
}

class _FitsOperationsScreenState extends State<FitsOperationsScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _entityController = TextEditingController(text: 'northshore-001');
  final TextEditingController _queryController = TextEditingController(text: 'verified');

  Map<String, dynamic>? _inspectResult;
  Map<String, dynamic>? _directSearchResult;
  Map<String, dynamic>? _indexSearchResult;
  Map<String, dynamic>? _indexResult;
  bool _loading = false;

  @override
  void dispose() {
    _entityController.dispose();
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _run(Future<Map<String, dynamic>> Function() action, void Function(Map<String, dynamic>) assign) async {
    setState(() => _loading = true);
    try {
      final result = await action();
      setState(() => assign(result));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Operation failed: $error')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('FITS operations', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Inspect, search and index directly from the current per-entity FITS evidence container.'),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _entityController,
                          decoration: const InputDecoration(
                            labelText: 'Entity external ID or UUID',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                        onPressed: _loading
                            ? null
                            : () => _run(
                                  () => _apiClient.inspectEntityFits(_entityController.text.trim()),
                                  (result) => _inspectResult = result,
                                ),
                        icon: const Icon(Icons.visibility_outlined),
                        label: const Text('Inspect FITS'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: _loading
                            ? null
                            : () => _run(
                                  () => _apiClient.rebuildFitsIndex(entityExternalId: _entityController.text.trim()),
                                  (result) => _indexResult = result,
                                ),
                        icon: const Icon(Icons.manage_search_outlined),
                        label: const Text('Rebuild index'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _queryController,
                          decoration: const InputDecoration(
                            labelText: 'Search query',
                            border: OutlineInputBorder(),
                          ),
                          onSubmitted: (_) => _run(
                            () => _apiClient.searchEntityFits(_entityController.text.trim(), _queryController.text.trim()),
                            (result) => _directSearchResult = result,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                        onPressed: _loading
                            ? null
                            : () => _run(
                                  () => _apiClient.searchEntityFits(_entityController.text.trim(), _queryController.text.trim()),
                                  (result) => _directSearchResult = result,
                                ),
                        icon: const Icon(Icons.search),
                        label: const Text('Direct search'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: _loading
                            ? null
                            : () => _run(
                                  () => _apiClient.searchFitsIndex(
                                    query: _queryController.text.trim(),
                                    entityExternalId: _entityController.text.trim(),
                                  ),
                                  (result) => _indexSearchResult = result,
                                ),
                        icon: const Icon(Icons.saved_search),
                        label: const Text('Index search'),
                      ),
                    ],
                  ),
                  if (_loading) ...[
                    const SizedBox(height: 16),
                    const LinearProgressIndicator(),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: ListView(
              children: [
                if (_inspectResult != null) _InspectionPanel(result: _inspectResult!),
                if (_directSearchResult != null) ...[
                  const SizedBox(height: 16),
                  _SearchPanel(title: 'Direct FITS search', result: _directSearchResult!),
                ],
                if (_indexSearchResult != null) ...[
                  const SizedBox(height: 16),
                  _SearchPanel(title: 'Index-backed FITS search', result: _indexSearchResult!),
                ],
                if (_indexResult != null) ...[
                  const SizedBox(height: 16),
                  _IndexPanel(result: _indexResult!),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _InspectionPanel extends StatelessWidget {
  const _InspectionPanel({required this.result});

  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final hduNames = (result['hdu_names'] as List<dynamic>? ?? <dynamic>[]).join(', ');
    final manifest = result['manifest'] as List<dynamic>? ?? <dynamic>[];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('FITS inspection', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            _DetailRow(label: 'Storage URI', value: '${result['storage_uri']}'),
            _DetailRow(label: 'Version', value: '${result['version_number']}'),
            _DetailRow(label: 'HDU count', value: '${result['hdu_count']}'),
            _DetailRow(label: 'HDUs', value: hduNames),
            const SizedBox(height: 12),
            Text('Manifest objects: ${manifest.length}'),
          ],
        ),
      ),
    );
  }
}

class _SearchPanel extends StatelessWidget {
  const _SearchPanel({required this.title, required this.result});

  final String title;
  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final results = result['results'] as List<dynamic>? ?? <dynamic>[];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text('Results: ${result['result_count']} from container ${result['container_version_id'] ?? '-'}'),
            const SizedBox(height: 12),
            if (results.isEmpty)
              const Text('No FITS matches found.')
            else
              ...results.map((item) {
                final row = item as Map<String, dynamic>;
                return ListTile(
                  leading: const Icon(Icons.description_outlined),
                  title: Text('${row['filename']} - ${row['hdu_name']}'),
                  subtitle: SelectableText(
                    'Object: ${row['object_type']} from ${row['source_system']}\n'
                    'Evidence ID: ${row['evidence_object_id']}\n'
                    '${row['snippet'] ?? ''}',
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

class _IndexPanel extends StatelessWidget {
  const _IndexPanel({required this.result});

  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('FITS index rebuild', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            _DetailRow(label: 'Indexed entities', value: '${result['indexed_entity_count']}'),
            _DetailRow(label: 'Skipped entities', value: '${result['skipped_entity_count']}'),
            SelectableText('${result['indexed']}'),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 120, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700))),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }
}
