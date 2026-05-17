import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class EntitiesScreen extends StatefulWidget {
  const EntitiesScreen({super.key});

  @override
  State<EntitiesScreen> createState() => _EntitiesScreenState();
}

class _EntitiesScreenState extends State<EntitiesScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _future;

  final TextEditingController _externalIdController = TextEditingController(text: 'northshore-001');
  final TextEditingController _displayNameController = TextEditingController(text: 'Northshore Trust - Client 001');
  final TextEditingController _filenameController = TextEditingController(text: 'proof-of-address.txt');
  final TextEditingController _textController = TextEditingController(
    text: 'Proof of address received and validated for Northshore Trust Client 001.',
  );

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getEntities();
  }

  @override
  void dispose() {
    _externalIdController.dispose();
    _displayNameController.dispose();
    _filenameController.dispose();
    _textController.dispose();
    super.dispose();
  }

  Future<void> _ingestNow() async {
    await _apiClient.ingestTextEvidence(
      entityExternalId: _externalIdController.text.trim(),
      entityDisplayName: _displayNameController.text.trim(),
      objectType: 'document',
      sourceSystem: 'flutter_manual_ingestion',
      filename: _filenameController.text.trim(),
      text: _textController.text,
    );
    setState(() => _future = _apiClient.getEntities());
  }

  Future<void> _queueIngestion() async {
    await _apiClient.createTextIngestionJob(
      entityExternalId: _externalIdController.text.trim(),
      entityDisplayName: _displayNameController.text.trim(),
      filename: _filenameController.text.trim(),
      text: _textController.text,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Queued ingestion job submitted')),
    );
  }

  Future<void> _rebuildContainer(Map<String, dynamic> entity) async {
    final result = await _apiClient.rebuildEntityContainer('${entity['external_id']}');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Built container v${result['version_number']} for ${entity['external_id']}')),
    );
  }

  Future<void> _queueContainerRebuild(Map<String, dynamic> entity) async {
    await _apiClient.queueEntityContainerRebuild('${entity['external_id']}');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Queued container rebuild for ${entity['external_id']}')),
    );
  }

  Future<void> _showEvidence(Map<String, dynamic> entity) async {
    final evidenceObjects = await _apiClient.getEntityEvidence('${entity['id']}');
    if (!mounted) return;

    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text('${entity['display_name']} evidence'),
          content: SizedBox(
            width: 700,
            child: evidenceObjects.isEmpty
                ? const Text('No evidence objects found.')
                : ListView.separated(
                    shrinkWrap: true,
                    itemCount: evidenceObjects.length,
                    separatorBuilder: (_, __) => const Divider(),
                    itemBuilder: (context, index) {
                      final evidence = evidenceObjects[index] as Map<String, dynamic>;
                      return ListTile(
                        leading: const Icon(Icons.description_outlined),
                        title: Text('${evidence['object_type']} from ${evidence['source_system']}'),
                        subtitle: Text(
                          'URI: ${evidence['storage_uri']}\nSHA-256: ${evidence['sha256']}',
                        ),
                      );
                    },
                  ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
          ],
        );
      },
    );
  }

  Future<void> _showContainerVersions(Map<String, dynamic> entity) async {
    final versions = await _apiClient.getEntityContainerVersions('${entity['external_id']}');
    if (!mounted) return;

    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text('${entity['display_name']} containers'),
          content: SizedBox(
            width: 820,
            child: versions.isEmpty
                ? const Text('No container versions found.')
                : ListView.separated(
                    shrinkWrap: true,
                    itemCount: versions.length,
                    separatorBuilder: (_, __) => const Divider(),
                    itemBuilder: (context, index) {
                      final version = versions[index] as Map<String, dynamic>;
                      return ListTile(
                        leading: const Icon(Icons.archive_outlined),
                        title: Text('Version ${version['version_number']} - ${version['status']}'),
                        subtitle: SelectableText(
                          'URI: ${version['storage_uri']}\n'
                          'SHA-256: ${version['sha256']}\n'
                          'Evidence objects: ${version['evidence_object_count']}\n'
                          'Size: ${version['size_bytes']} bytes',
                        ),
                      );
                    },
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
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 420,
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('Ingest evidence', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _externalIdController,
                      decoration: const InputDecoration(labelText: 'Entity external ID'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _displayNameController,
                      decoration: const InputDecoration(labelText: 'Entity display name'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _filenameController,
                      decoration: const InputDecoration(labelText: 'Filename'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _textController,
                      minLines: 6,
                      maxLines: 8,
                      decoration: const InputDecoration(
                        labelText: 'Evidence text',
                        alignLabelWithHint: true,
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: _ingestNow,
                            icon: const Icon(Icons.upload_file),
                            label: const Text('Ingest now'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _queueIngestion,
                            icon: const Icon(Icons.schedule_send),
                            label: const Text('Queue job'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: 24),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Entities', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 8),
                          const Text('Customer/entity records created from ingested evidence.'),
                        ],
                      ),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => setState(() => _future = _apiClient.getEntities()),
                      icon: const Icon(Icons.refresh),
                      label: const Text('Refresh'),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Expanded(
                  child: FutureBuilder<List<dynamic>>(
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (snapshot.hasError) {
                        return Center(child: Text('Unable to load entities: ${snapshot.error}'));
                      }
                      final entities = snapshot.data ?? <dynamic>[];
                      if (entities.isEmpty) {
                        return const Center(child: Text('No entities have been created yet.'));
                      }
                      return ListView.separated(
                        itemCount: entities.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final entity = entities[index] as Map<String, dynamic>;
                          return Card(
                            child: Padding(
                              padding: const EdgeInsets.all(8),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  ListTile(
                                    leading: const Icon(Icons.business_outlined),
                                    title: Text('${entity['display_name']}'),
                                    subtitle: Text('External ID: ${entity['external_id']}\nStatus: ${entity['status']}'),
                                  ),
                                  Padding(
                                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                                    child: Wrap(
                                      spacing: 8,
                                      runSpacing: 8,
                                      children: [
                                        TextButton.icon(
                                          onPressed: () => _showEvidence(entity),
                                          icon: const Icon(Icons.folder_open),
                                          label: const Text('Evidence'),
                                        ),
                                        TextButton.icon(
                                          onPressed: () => _rebuildContainer(entity),
                                          icon: const Icon(Icons.archive_outlined),
                                          label: const Text('Rebuild container'),
                                        ),
                                        TextButton.icon(
                                          onPressed: () => _queueContainerRebuild(entity),
                                          icon: const Icon(Icons.schedule_send),
                                          label: const Text('Queue rebuild'),
                                        ),
                                        TextButton.icon(
                                          onPressed: () => _showContainerVersions(entity),
                                          icon: const Icon(Icons.history),
                                          label: const Text('Container versions'),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
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
          ),
        ],
      ),
    );
  }
}
