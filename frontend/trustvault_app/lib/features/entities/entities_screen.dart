import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/evidence_pdf_viewer.dart';
import '../../shared/selected_customer.dart';
import '../../shared/trustvault_data_grid.dart';

class EntitiesScreen extends StatefulWidget {
  const EntitiesScreen({super.key});

  @override
  State<EntitiesScreen> createState() => _EntitiesScreenState();
}

class _EntitiesScreenState extends State<EntitiesScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getCustomers();
  }

  Future<void> _rebuildContainer(Map<String, dynamic> entity) async {
    final result =
        await _apiClient.rebuildEntityContainer('${entity['external_id']}');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
            'Built FITS archive v${result['version_number']} for ${entity['external_id']}')));
    setState(() => _future = _apiClient.getCustomers());
  }

  Future<void> _queueContainerRebuild(Map<String, dynamic> entity) async {
    await _apiClient.queueEntityContainerRebuild('${entity['external_id']}');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content:
            Text('Queued FITS archive rebuild for ${entity['external_id']}')));
  }

  Future<void> _validateContainerVersion(Map<String, dynamic> version) async {
    final result =
        await _apiClient.validateContainerVersion('${version['id']}');
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) {
        final payloadResults =
            (result['payload_results'] as List<dynamic>? ?? <dynamic>[])
                .cast<Map<String, dynamic>>();
        final isValid = result['overall_status'] == 'valid';
        return AlertDialog(
          title: Row(children: [
            Icon(isValid ? Icons.verified_outlined : Icons.error_outline),
            const SizedBox(width: 8),
            Text('Validation: ${result['overall_status']}')
          ]),
          content: SizedBox(
            width: 980,
            height: 620,
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              _DetailRow(
                  label: 'Storage URI', value: '${result['storage_uri']}'),
              _DetailRow(
                  label: 'Container hash',
                  value: '${result['container_hash_matches']}'),
              _DetailRow(
                  label: 'Size matches', value: '${result['size_matches']}'),
              _DetailRow(
                  label: 'FITS opened', value: '${result['fits_opened']}'),
              _DetailRow(
                  label: 'Missing HDUs',
                  value: '${result['missing_required_hdus']}'),
              const SizedBox(height: 12),
              Expanded(
                child: TrustVaultDataGrid(
                  title: 'Payload validation',
                  rows: payloadResults,
                  columns: const [
                    TrustVaultDataGridColumn(
                        key: 'hdu_name', label: 'HDU', width: 180),
                    TrustVaultDataGridColumn(
                        key: 'filename', label: 'Filename', width: 260),
                    TrustVaultDataGridColumn(
                        key: 'valid', label: 'Valid', width: 90),
                    TrustVaultDataGridColumn(
                        key: 'expected_sha256',
                        label: 'Expected SHA-256',
                        width: 320),
                    TrustVaultDataGridColumn(
                        key: 'actual_sha256',
                        label: 'Actual SHA-256',
                        width: 320),
                    TrustVaultDataGridColumn(
                        key: 'header_sha256',
                        label: 'Header SHA-256',
                        width: 320,
                        visibleByDefault: false),
                  ],
                  exportFilename: 'trustvault-payload-validation.csv',
                  height: 360,
                  dense: true,
                ),
              ),
            ]),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Close'))
          ],
        );
      },
    );
  }

  Future<void> _showEvidence(Map<String, dynamic> entity) async {
    SelectedCustomerController.select(entity);
    final evidenceObjects = await _apiClient
        .getEntityEvidence('${entity['id'] ?? entity['external_id']}');
    if (!mounted) return;
    final rows = evidenceObjects.cast<Map<String, dynamic>>().map((evidence) {
      final metadata = evidence['metadata_json'] as Map<String, dynamic>? ??
          <String, dynamic>{};
      return <String, dynamic>{
        ...evidence,
        'filename': metadata['filename'] ??
            metadata['original_filename'] ??
            evidence['storage_uri'] ??
            '-',
        'category': metadata['category'],
        'document_type': metadata['document_type'],
        'retention_class': metadata['retention_class'],
        'legal_hold_status': metadata['legal_hold_status'],
      };
    }).toList();
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title:
            Text('${entity['display_name'] ?? entity['external_id']} evidence'),
        content: SizedBox(
          width: 1180,
          height: 720,
          child: TrustVaultDataGrid(
            title: 'Evidence objects',
            rows: rows,
            columns: const [
              TrustVaultDataGridColumn(
                  key: 'filename', label: 'Filename', width: 260),
              TrustVaultDataGridColumn(
                  key: 'object_type', label: 'Type', width: 140),
              TrustVaultDataGridColumn(
                  key: 'category', label: 'Category', width: 160),
              TrustVaultDataGridColumn(
                  key: 'document_type', label: 'Document type', width: 180),
              TrustVaultDataGridColumn(
                  key: 'source_system', label: 'Source', width: 180),
              TrustVaultDataGridColumn(
                  key: 'content_type', label: 'Content type', width: 160),
              TrustVaultDataGridColumn(
                  key: 'retention_class',
                  label: 'Retention class',
                  width: 160,
                  visibleByDefault: false),
              TrustVaultDataGridColumn(
                  key: 'legal_hold_status',
                  label: 'Legal hold',
                  width: 130,
                  visibleByDefault: false),
              TrustVaultDataGridColumn(
                  key: 'sha256', label: 'SHA-256', width: 320),
            ],
            onRowTap: _showEvidencePreview,
            exportFilename: 'trustvault-entity-evidence.csv',
            height: 560,
            dense: true,
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'))
        ],
      ),
    );
  }

  Future<void> _showEvidencePreview(Map<String, dynamic> evidence) async {
    final objectId =
        '${evidence['id'] ?? evidence['evidence_object_id'] ?? ''}';
    if (objectId.isEmpty || objectId == 'null') return;
    final preview = await _apiClient.getEvidencePreview(objectId);
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
            '${preview['filename'] ?? evidence['storage_uri'] ?? 'Evidence preview'}'),
        content: SizedBox(
            width: 920,
            height: 700,
            child:
                _EvidencePreviewBody(apiClient: _apiClient, preview: preview)),
        actions: [
          TextButton.icon(
              onPressed: () => _open(_apiClient.evidenceFileUrl(objectId)),
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open')),
          TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close')),
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
                actions: [
                  TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('Close'))
                ]));
  }

  Future<void> _showContainerVersions(Map<String, dynamic> entity) async {
    final versions =
        await _apiClient.getEntityContainerVersions('${entity['external_id']}');
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${entity['display_name']} FITS archive versions'),
        content: SizedBox(
          width: 1080,
          height: 620,
          child: TrustVaultDataGrid(
            title: 'FITS archive versions',
            rows: versions.cast<Map<String, dynamic>>(),
            columns: const [
              TrustVaultDataGridColumn(
                  key: 'version_number', label: 'Version', width: 100),
              TrustVaultDataGridColumn(
                  key: 'status', label: 'Status', width: 120),
              TrustVaultDataGridColumn(
                  key: 'evidence_object_count', label: 'Evidence', width: 100),
              TrustVaultDataGridColumn(
                  key: 'size_bytes', label: 'Size bytes', width: 120),
              TrustVaultDataGridColumn(
                  key: 'storage_uri', label: 'Storage URI', width: 460),
              TrustVaultDataGridColumn(
                  key: 'sha256',
                  label: 'SHA-256',
                  width: 320,
                  visibleByDefault: false),
            ],
            onRowTap: _validateContainerVersion,
            exportFilename: 'trustvault-fits-versions.csv',
            height: 460,
            dense: true,
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'))
        ],
      ),
    );
  }

  void _searchEntity(Map<String, dynamic> entity) {
    SelectedCustomerController.requestSearchForSelectedEntity(entity);
    context.go('/search');
  }

  void _handleAction(Map<String, dynamic> entity, String value) {
    if (value == 'evidence') _showEvidence(entity);
    if (value == 'versions') _showContainerVersions(entity);
    if (value == 'rebuild') _rebuildContainer(entity);
    if (value == 'queue') _queueContainerRebuild(entity);
    if (value == 'completeness') {
      SelectedCustomerController.select(entity);
      context.go('/completeness');
    }
    if (value == 'search') _searchEntity(entity);
  }

  List<TrustVaultDataGridColumn> _columns() => [
        const TrustVaultDataGridColumn(
            key: 'external_id', label: 'Entity ID', width: 130),
        const TrustVaultDataGridColumn(
            key: 'display_name', label: 'Name', width: 240),
        const TrustVaultDataGridColumn(
            key: 'risk_rating', label: 'Risk', width: 100),
        const TrustVaultDataGridColumn(
            key: 'jurisdiction', label: 'Jurisdiction', width: 140),
        const TrustVaultDataGridColumn(
            key: 'entity_type',
            label: 'Type',
            width: 130,
            visibleByDefault: false),
        const TrustVaultDataGridColumn(
            key: 'status',
            label: 'Status',
            width: 110,
            visibleByDefault: false),
        const TrustVaultDataGridColumn(
            key: 'evidence_object_count', label: 'Evidence', width: 100),
        TrustVaultDataGridColumn(
            key: 'has_current_fits_container',
            label: 'Current FITS',
            width: 120,
            cellBuilder: (row) => _StatusPill(
                label: row['has_current_fits_container'] == true ? 'Yes' : 'No',
                positive: row['has_current_fits_container'] == true)),
        const TrustVaultDataGridColumn(
            key: 'current_container_version_number',
            label: 'Version',
            width: 100),
        TrustVaultDataGridColumn(
            key: 'actions',
            label: 'Actions',
            width: 70,
            sortable: false,
            valueBuilder: (_) => '',
            cellBuilder: (row) => PopupMenuButton<String>(
                tooltip: 'Actions',
                onSelected: (value) => _handleAction(row, value),
                itemBuilder: (context) => const [
                      PopupMenuItem(
                          value: 'evidence', child: Text('View evidence')),
                      PopupMenuItem(
                          value: 'versions', child: Text('FITS versions')),
                      PopupMenuItem(
                          value: 'search', child: Text('Search this entity')),
                      PopupMenuItem(
                          value: 'completeness', child: Text('Completeness')),
                      PopupMenuDivider(),
                      PopupMenuItem(
                          value: 'rebuild', child: Text('Rebuild FITS now')),
                      PopupMenuItem(
                          value: 'queue', child: Text('Queue rebuild'))
                    ])),
      ];

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text('Entities',
                      style: Theme.of(context)
                          .textTheme
                          .displaySmall
                          ?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  const Text(
                      'Entity records and their current FITS evidence archive lifecycle. Click a row to view the evidence list.')
                ])),
            OutlinedButton.icon(
                onPressed: () =>
                    setState(() => _future = _apiClient.getCustomers()),
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh'))
          ]),
          const SizedBox(height: 16),
          FutureBuilder<List<dynamic>>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done)
                return const SizedBox(
                    height: 520,
                    child: Center(child: CircularProgressIndicator()));
              if (snapshot.hasError)
                return SizedBox(
                    height: 520,
                    child: Center(
                        child: Text(
                            'Unable to load entities: ${snapshot.error}')));
              final rows =
                  (snapshot.data ?? <dynamic>[]).cast<Map<String, dynamic>>();
              return TrustVaultDataGrid(
                  title: 'Entities',
                  subtitle:
                      'Search, sort, show/hide columns and export entity records.',
                  rows: rows,
                  columns: _columns(),
                  initialSortColumnKey: 'external_id',
                  onRowTap: _showEvidence,
                  exportFilename: 'trustvault-entities.csv',
                  emptyText: 'No matching entities.',
                  height: 640,
                  dense: true);
            },
          ),
          const SizedBox(height: 32),
        ]),
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
    if (kind == 'image')
      return InteractiveViewer(
          child: Center(
              child: Image.network(apiClient.evidenceFileUrl(objectId),
                  fit: BoxFit.contain)));
    if (kind == 'pdf')
      return EvidencePdfViewer(
          apiClient: apiClient, evidenceObjectId: objectId);
    final text = preview['safe_preview'] ?? preview['text_preview'];
    if (kind == 'eml' || kind == 'text')
      return SingleChildScrollView(child: SelectableText('$text'));
    return Center(
        child: Text(
            'No inline preview is available for ${preview['content_type'] ?? 'this file type'}'));
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
        decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            color: positive ? scheme.primaryContainer : scheme.errorContainer),
        child: Text(label,
            style: TextStyle(
                color: positive
                    ? scheme.onPrimaryContainer
                    : scheme.onErrorContainer)));
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
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(
              width: 140,
              child: Text(label,
                  style: const TextStyle(fontWeight: FontWeight.w700))),
          Expanded(child: SelectableText(value))
        ]));
  }
}
