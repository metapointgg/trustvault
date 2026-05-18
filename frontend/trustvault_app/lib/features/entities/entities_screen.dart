import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class EntitiesScreen extends StatefulWidget {
  const EntitiesScreen({super.key});

  @override
  State<EntitiesScreen> createState() => _EntitiesScreenState();
}

class _EntitiesScreenState extends State<EntitiesScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _filterController = TextEditingController();
  late Future<List<dynamic>> _future;
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getCustomers();
    _filterController.addListener(() => setState(() => _filter = _filterController.text.trim().toLowerCase()));
  }

  @override
  void dispose() {
    _filterController.dispose();
    super.dispose();
  }

  Future<void> _rebuildContainer(Map<String, dynamic> entity) async {
    final result = await _apiClient.rebuildEntityContainer('${entity['external_id']}');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Built FITS archive v${result['version_number']} for ${entity['external_id']}')));
    setState(() => _future = _apiClient.getCustomers());
  }

  Future<void> _queueContainerRebuild(Map<String, dynamic> entity) async {
    await _apiClient.queueEntityContainerRebuild('${entity['external_id']}');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Queued FITS archive rebuild for ${entity['external_id']}')));
  }

  Future<void> _validateContainerVersion(Map<String, dynamic> version) async {
    final result = await _apiClient.validateContainerVersion('${version['id']}');
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) {
        final payloadResults = (result['payload_results'] as List<dynamic>? ?? <dynamic>[]).cast<dynamic>();
        final isValid = result['overall_status'] == 'valid';
        return AlertDialog(
          title: Row(children: [Icon(isValid ? Icons.verified_outlined : Icons.error_outline), const SizedBox(width: 8), Text('Validation: ${result['overall_status']}')]),
          content: SizedBox(
            width: 820,
            child: SingleChildScrollView(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                _DetailRow(label: 'Storage URI', value: '${result['storage_uri']}'),
                _DetailRow(label: 'Container hash', value: '${result['container_hash_matches']}'),
                _DetailRow(label: 'Size matches', value: '${result['size_matches']}'),
                _DetailRow(label: 'FITS opened', value: '${result['fits_opened']}'),
                _DetailRow(label: 'Missing HDUs', value: '${result['missing_required_hdus']}'),
                const SizedBox(height: 12),
                Text('Payload validation', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                if (payloadResults.isEmpty)
                  const Text('No payload results returned.')
                else
                  SizedBox(
                    height: 340,
                    child: SingleChildScrollView(
                      child: Column(
                        children: payloadResults.map((item) {
                          final payload = item as Map<String, dynamic>;
                          return Card(
                            child: ListTile(
                              dense: true,
                              leading: Icon(payload['valid'] == true ? Icons.check_circle_outline : Icons.error_outline),
                              title: Text('${payload['hdu_name']} - ${payload['filename']}'),
                              subtitle: SelectableText('Expected: ${payload['expected_sha256']}\nActual: ${payload['actual_sha256']}\nHeader: ${payload['header_sha256']}\nValid: ${payload['valid']}'),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                  ),
              ]),
            ),
          ),
          actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
        );
      },
    );
  }

  Future<void> _showEvidence(Map<String, dynamic> entity) async {
    SelectedCustomerController.select(entity);
    final evidenceObjects = await _apiClient.getEntityEvidence('${entity['id'] ?? entity['external_id']}');
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${entity['display_name'] ?? entity['external_id']} evidence'),
        content: SizedBox(
          width: 1180,
          height: 680,
          child: evidenceObjects.isEmpty
              ? const Text('No evidence objects found.')
              : SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: SingleChildScrollView(
                    child: DataTable(
                      showCheckboxColumn: false,
                      columns: const [
                        DataColumn(label: Text('Filename')),
                        DataColumn(label: Text('Type')),
                        DataColumn(label: Text('Category')),
                        DataColumn(label: Text('Document type')),
                        DataColumn(label: Text('Source')),
                        DataColumn(label: Text('Content type')),
                        DataColumn(label: Text('SHA-256')),
                        DataColumn(label: Text('Actions')),
                      ],
                      rows: evidenceObjects.cast<Map<String, dynamic>>().map((evidence) {
                        final metadata = evidence['metadata_json'] as Map<String, dynamic>? ?? <String, dynamic>{};
                        final filename = metadata['filename'] ?? metadata['original_filename'] ?? evidence['storage_uri'] ?? '-';
                        return DataRow(
                          onSelectChanged: (_) => _showEvidencePreview(evidence),
                          cells: [
                            DataCell(SizedBox(width: 260, child: Text('$filename', overflow: TextOverflow.ellipsis))),
                            DataCell(Text('${evidence['object_type'] ?? '-'}')),
                            DataCell(Text('${metadata['category'] ?? '-'}')),
                            DataCell(Text('${metadata['document_type'] ?? '-'}')),
                            DataCell(Text('${evidence['source_system'] ?? '-'}')),
                            DataCell(Text('${evidence['content_type'] ?? '-'}')),
                            DataCell(SizedBox(width: 320, child: SelectableText('${evidence['sha256'] ?? '-'}'))),
                            DataCell(TextButton.icon(onPressed: () => _showEvidencePreview(evidence), icon: const Icon(Icons.visibility_outlined), label: const Text('Open'))),
                          ],
                        );
                      }).toList(),
                    ),
                  ),
                ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  Future<void> _showEvidencePreview(Map<String, dynamic> evidence) async {
    final objectId = '${evidence['id'] ?? evidence['evidence_object_id'] ?? ''}';
    if (objectId.isEmpty || objectId == 'null') return;
    final preview = await _apiClient.getEvidencePreview(objectId);
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${preview['filename'] ?? evidence['storage_uri'] ?? 'Evidence preview'}'),
        content: SizedBox(width: 920, height: 700, child: _EvidencePreviewBody(apiClient: _apiClient, preview: preview)),
        actions: [
          TextButton.icon(onPressed: () => _open(_apiClient.evidenceFileUrl(objectId)), icon: const Icon(Icons.open_in_new), label: const Text('Open')),
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
        ],
      ),
    );
  }

  Future<void> _open(String url) async {
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Open evidence'),
        content: SelectableText(url),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  Future<void> _showContainerVersions(Map<String, dynamic> entity) async {
    final versions = await _apiClient.getEntityContainerVersions('${entity['external_id']}');
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${entity['display_name']} FITS archive versions'),
        content: SizedBox(
          width: 980,
          height: 520,
          child: versions.isEmpty
              ? const Text('No FITS archive versions found.')
              : SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: SingleChildScrollView(
                    child: DataTable(
                      columns: const [
                        DataColumn(label: Text('Version')),
                        DataColumn(label: Text('Status')),
                        DataColumn(label: Text('Evidence')),
                        DataColumn(label: Text('Size')),
                        DataColumn(label: Text('Storage URI')),
                        DataColumn(label: Text('Actions')),
                      ],
                      rows: versions.cast<Map<String, dynamic>>().map((version) {
                        final isFits = '${version['storage_uri']}'.toLowerCase().endsWith('.fits');
                        return DataRow(cells: [
                          DataCell(Text('${version['version_number'] ?? '-'}')),
                          DataCell(Text('${version['status'] ?? '-'}')),
                          DataCell(Text('${version['evidence_object_count'] ?? '-'}')),
                          DataCell(Text('${version['size_bytes'] ?? '-'} bytes')),
                          DataCell(SizedBox(width: 420, child: SelectableText('${version['storage_uri'] ?? '-'}'))),
                          DataCell(TextButton.icon(onPressed: isFits ? () => _validateContainerVersion(version) : null, icon: const Icon(Icons.verified_outlined), label: const Text('Validate'))),
                        ]);
                      }).toList(),
                    ),
                  ),
                ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  void _searchEntity(Map<String, dynamic> entity) {
    SelectedCustomerController.requestSearchForSelectedEntity(entity);
    context.go('/search');
  }

  List<Map<String, dynamic>> _filtered(List<dynamic> rows) {
    final castRows = rows.cast<Map<String, dynamic>>();
    if (_filter.isEmpty) return castRows;
    return castRows.where((row) {
      final haystack = '${row['external_id']} ${row['display_name']} ${row['risk_rating']} ${row['jurisdiction']}'.toLowerCase();
      return haystack.contains(_filter);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Entities', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                const Text('Entity records and their current FITS evidence archive lifecycle. Click a row to view the evidence list.'),
              ]),
            ),
            OutlinedButton.icon(onPressed: () => setState(() => _future = _apiClient.getCustomers()), icon: const Icon(Icons.refresh), label: const Text('Refresh')),
          ]),
          const SizedBox(height: 16),
          TextField(controller: _filterController, decoration: const InputDecoration(border: OutlineInputBorder(), prefixIcon: Icon(Icons.search), labelText: 'Search entities by name, ID, risk or jurisdiction')),
          const SizedBox(height: 16),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError) return Center(child: Text('Unable to load entities: ${snapshot.error}'));
                final entities = _filtered(snapshot.data ?? <dynamic>[]);
                if (entities.isEmpty) return const Center(child: Text('No matching entities.'));
                return Card(
                  child: Scrollbar(
                    thumbVisibility: true,
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: SingleChildScrollView(
                        child: DataTable(
                          showCheckboxColumn: false,
                          columns: const [
                            DataColumn(label: Text('Entity ID')),
                            DataColumn(label: Text('Name')),
                            DataColumn(label: Text('Risk')),
                            DataColumn(label: Text('Jurisdiction')),
                            DataColumn(label: Text('Evidence')),
                            DataColumn(label: Text('Current FITS')),
                            DataColumn(label: Text('Version')),
                            DataColumn(label: Text('Actions')),
                          ],
                          rows: entities.map((entity) {
                            final hasFits = entity['has_current_fits_container'] == true;
                            return DataRow(
                              onSelectChanged: (_) => _showEvidence(entity),
                              cells: [
                                DataCell(Text('${entity['external_id'] ?? '-'}')),
                                DataCell(SizedBox(width: 220, child: Text('${entity['display_name'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                DataCell(Text('${entity['risk_rating'] ?? '-'}')),
                                DataCell(Text('${entity['jurisdiction'] ?? '-'}')),
                                DataCell(Text('${entity['evidence_object_count'] ?? 0}')),
                                DataCell(_StatusPill(label: hasFits ? 'Yes' : 'No', positive: hasFits)),
                                DataCell(Text('${entity['current_container_version_number'] ?? '-'}')),
                                DataCell(PopupMenuButton<String>(
                                  tooltip: 'Actions',
                                  onSelected: (value) {
                                    if (value == 'evidence') _showEvidence(entity);
                                    if (value == 'versions') _showContainerVersions(entity);
                                    if (value == 'rebuild') _rebuildContainer(entity);
                                    if (value == 'queue') _queueContainerRebuild(entity);
                                    if (value == 'completeness') {
                                      SelectedCustomerController.select(entity);
                                      context.go('/completeness');
                                    }
                                    if (value == 'search') _searchEntity(entity);
                                  },
                                  itemBuilder: (context) => const [
                                    PopupMenuItem(value: 'evidence', child: Text('View evidence')),
                                    PopupMenuItem(value: 'versions', child: Text('FITS versions')),
                                    PopupMenuItem(value: 'search', child: Text('Search this entity')),
                                    PopupMenuItem(value: 'completeness', child: Text('Completeness')),
                                    PopupMenuDivider(),
                                    PopupMenuItem(value: 'rebuild', child: Text('Rebuild FITS now')),
                                    PopupMenuItem(value: 'queue', child: Text('Queue rebuild')),
                                  ],
                                )),
                              ],
                            );
                          }).toList(),
                        ),
                      ),
                    ),
                  ),
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
    if (kind == 'image') return InteractiveViewer(child: Center(child: Image.network(apiClient.evidenceFileUrl(objectId), fit: BoxFit.contain)));
    if (kind == 'pdf') return Center(child: FilledButton.icon(onPressed: null, icon: const Icon(Icons.picture_as_pdf_outlined), label: const Text('Use Open to view PDF in a new tab')));
    final text = preview['safe_preview'] ?? preview['text_preview'];
    if (kind == 'eml' || kind == 'text') return SingleChildScrollView(child: SelectableText('$text'));
    return Center(child: Text('No inline preview is available for ${preview['content_type'] ?? 'this file type'}'));
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.label, required this.positive});

  final String label;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: positive ? scheme.primaryContainer : scheme.errorContainer),
      child: Text(label, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
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
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [SizedBox(width: 140, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700))), Expanded(child: SelectableText(value))]),
    );
  }
}
