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
  Map<String, dynamic>? _result;
  String? _error;

  Future<void> _pickAndUpload() async {
    setState(() {
      _uploading = true;
      _error = null;
      _result = null;
    });
    try {
      final picked = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['zip'],
        withData: true,
      );
      if (picked == null || picked.files.isEmpty) {
        setState(() {
          _uploading = false;
        });
        return;
      }
      final file = picked.files.single;
      final bytes = file.bytes;
      if (bytes == null) {
        throw StateError('No file bytes were returned by the browser picker.');
      }
      final result = await _apiClient.uploadSourceFolderZip(filename: file.name, bytes: bytes);
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
      if (!mounted) return;
      setState(() {
        _result = result;
        _uploading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _uploading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Ingestion', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Upload a production-style customer source folder ZIP. TrustVault will preserve payloads, build the FITS archive and rebuild the index.'),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('Source folder upload', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 8),
                  const Text('Expected folders include metadata, documents, statements, emails, scans, extracts and large_evidence.'),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: _uploading ? null : _pickAndUpload,
                    icon: _uploading
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.upload_file),
                    label: Text(_uploading ? 'Uploading...' : 'Select and upload ZIP'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          if (_error != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            ),
          if (result != null) ...[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                Chip(label: Text('Customer: ${result['entity_external_id']}')),
                Chip(label: Text('Evidence inserted: ${result['evidence_object_count']}')),
                Chip(label: Text('Duplicates skipped: ${result['duplicate_count'] ?? 0}')),
                Chip(label: Text('Skipped: ${result['skipped_count']}')),
                Chip(label: Text('FITS rebuilt: ${result['container'] != null ? 'yes' : 'no'}')),
              ],
            ),
            if (result['message'] != null) ...[
              const SizedBox(height: 12),
              Text('${result['message']}', style: Theme.of(context).textTheme.bodyMedium),
            ],
            const SizedBox(height: 16),
            Expanded(
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: SingleChildScrollView(
                    child: SelectableText(const JsonEncoder.withIndent('  ').convert(result)),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
