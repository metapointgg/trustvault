import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class SourceFolderUploadScreen extends StatefulWidget {
  const SourceFolderUploadScreen({super.key});

  @override
  State<SourceFolderUploadScreen> createState() => _SourceFolderUploadScreenState();
}

class _SourceFolderUploadScreenState extends State<SourceFolderUploadScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  bool _uploading = false;
  final List<_UploadResult> _results = <_UploadResult>[];
  String? _error;

  Future<void> _pickAndUpload() async {
    setState(() {
      _uploading = true;
      _error = null;
      _results.clear();
    });
    try {
      final picked = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['zip'],
        withData: true,
        allowMultiple: true,
      );
      if (picked == null || picked.files.isEmpty) {
        setState(() => _uploading = false);
        return;
      }

      for (final file in picked.files) {
        final validation = _validateZipSelection(file.name, file.size);
        if (validation != null) {
          _results.add(_UploadResult(filename: file.name, status: 'failed pre-check', message: validation));
          continue;
        }
        final bytes = file.bytes;
        if (bytes == null) {
          _results.add(_UploadResult(filename: file.name, status: 'failed pre-check', message: 'No file bytes were returned by the browser picker.'));
          continue;
        }
        try {
          final result = await _apiClient.uploadSourceFolderZip(filename: file.name, bytes: bytes);
          _results.add(_UploadResult(filename: file.name, status: 'uploaded', payload: result));
          final externalId = result['entity_external_id']?.toString();
          if (externalId != null && externalId.isNotEmpty) {
            SelectedCustomerController.select(<String, dynamic>{
              'external_id': externalId,
              'display_name': result['entity_display_name'] ?? externalId,
              'id': result['entity_id'],
              'has_current_fits_container': result['container'] != null,
              'current_container_version_id': (result['container'] as Map<String, dynamic>?)?['container_version_id'],
              'current_container_version_number': (result['container'] as Map<String, dynamic>?)?['version_number'],
              'current_container_storage_uri': (result['container'] as Map<String, dynamic>?)?['storage_uri'],
            });
            SelectedCustomerController.requestRefresh();
          }
        } catch (error) {
          _results.add(_UploadResult(filename: file.name, status: 'failed upload', message: '$error'));
        }
        if (mounted) setState(() {});
      }
      if (!mounted) return;
      setState(() => _uploading = false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _uploading = false;
      });
    }
  }

  String? _validateZipSelection(String filename, int size) {
    if (!filename.toLowerCase().endsWith('.zip')) return 'Only .zip customer source-folder archives are accepted.';
    if (!RegExp(r'CUST-[0-9A-Za-z_-]+').hasMatch(filename)) return 'Filename should include the customer external ID, for example CUST-000001.zip.';
    if (size <= 0) return 'The selected ZIP is empty.';
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final uploaded = _results.where((result) => result.status == 'uploaded').length;
    final failed = _results.where((result) => result.status != 'uploaded').length;
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Ingestion', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  const Text('Upload one or more customer source-folder ZIPs. TrustVault checks the selected files, preserves payloads, builds FITS archives and rebuilds the index.'),
                ]),
              ),
              FilledButton.icon(
                onPressed: _uploading ? null : _pickAndUpload,
                icon: _uploading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.upload_file),
                label: Text(_uploading ? 'Uploading...' : 'Select ZIP files'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _StructureChecklist(),
          const SizedBox(height: 16),
          if (_error != null) Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)))),
          Wrap(spacing: 8, runSpacing: 8, children: [
            Chip(label: Text('Uploaded: $uploaded')),
            Chip(label: Text('Failed/pre-check failed: $failed')),
            Chip(label: Text('Total selected: ${_results.length}')),
          ]),
          const SizedBox(height: 16),
          Expanded(
            child: _results.isEmpty
                ? const Center(child: Text('Select one or more customer ZIPs to begin ingestion.'))
                : Card(
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: SingleChildScrollView(
                        child: DataTable(
                          columns: const [
                            DataColumn(label: Text('File')),
                            DataColumn(label: Text('Status')),
                            DataColumn(label: Text('Customer')),
                            DataColumn(label: Text('Evidence inserted')),
                            DataColumn(label: Text('Duplicates')),
                            DataColumn(label: Text('Skipped')),
                            DataColumn(label: Text('FITS rebuilt')),
                            DataColumn(label: Text('Message')),
                          ],
                          rows: _results.map((result) {
                            final payload = result.payload ?? <String, dynamic>{};
                            return DataRow(cells: [
                              DataCell(Text(result.filename)),
                              DataCell(_StatusPill(label: result.status, positive: result.status == 'uploaded')),
                              DataCell(Text('${payload['entity_external_id'] ?? '-'}')),
                              DataCell(Text('${payload['evidence_object_count'] ?? '-'}')),
                              DataCell(Text('${payload['duplicate_count'] ?? 0}')),
                              DataCell(Text('${payload['skipped_count'] ?? '-'}')),
                              DataCell(Text(payload['container'] != null ? 'Yes' : 'No')),
                              DataCell(SizedBox(width: 520, child: SelectableText(result.message ?? '${payload['message'] ?? const JsonEncoder.withIndent('  ').convert(payload)}'))),
                            ]);
                          }).toList(),
                        ),
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

class _StructureChecklist extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Source-folder ZIP structure check', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Client-side checks confirm ZIP extension, non-empty file and a customer ID in the filename. Server-side ingestion performs the authoritative structure validation.'),
          const SizedBox(height: 10),
          Wrap(spacing: 8, runSpacing: 8, children: const [
            Chip(label: Text('metadata/')),
            Chip(label: Text('documents/')),
            Chip(label: Text('statements/')),
            Chip(label: Text('emails/')),
            Chip(label: Text('scans/')),
            Chip(label: Text('extracts/')),
            Chip(label: Text('large_evidence/')),
          ]),
        ]),
      ),
    );
  }
}

class _UploadResult {
  const _UploadResult({required this.filename, required this.status, this.message, this.payload});

  final String filename;
  final String status;
  final String? message;
  final Map<String, dynamic>? payload;
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
