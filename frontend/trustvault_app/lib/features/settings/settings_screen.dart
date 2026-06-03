import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../core/auth/auth_controller.dart';
import 'demo_archive_settings_card.dart';
import 'industry_pack_editor_card.dart';
import 'industry_ruleset_settings_card.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<Map<String, dynamic>> _settingsFuture;
  late Future<Map<String, dynamic>> _autoIngestionFuture;
  late Future<Map<String, dynamic>> _documentClassificationFuture;
  Map<String, dynamic> _pendingUpdates = <String, dynamic>{};
  bool _saving = false;
  String? _message;
  String? _error;
  _SettingsSection _section = _SettingsSection.queryVocabulary;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _settingsFuture = _apiClient.getSettings();
    _autoIngestionFuture = _apiClient.getAutoIngestionStatus();
    _documentClassificationFuture = _apiClient.getDocumentClassificationSettings();
  }

  Future<void> _refresh() async {
    setState(() {
      _pendingUpdates = <String, dynamic>{};
      _message = null;
      _error = null;
      _reload();
    });
  }

  Future<void> _save() async {
    if (_pendingUpdates.isEmpty) return;
    setState(() {
      _saving = true;
      _message = null;
      _error = null;
    });
    try {
      final response = await _apiClient.updateSettings(_pendingUpdates);
      if (!mounted) return;
      setState(() {
        _message = 'Updated ${response['updated_count'] ?? _pendingUpdates.length} setting(s). Some changes may require API/worker restart if they affect process-level configuration.';
        _pendingUpdates = <String, dynamic>{};
        _saving = false;
        _reload();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _saving = false;
      });
    }
  }

  Future<void> _scanNow() async {
    setState(() {
      _message = null;
      _error = null;
    });
    try {
      final response = await _apiClient.scanAutoIngestionFolder();
      if (!mounted) return;
      setState(() {
        _message = 'Scan complete. Processed: ${response['processed_count'] ?? 0}; failed: ${response['failed_count'] ?? 0}.';
        _autoIngestionFuture = _apiClient.getAutoIngestionStatus();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = '$error');
    }
  }

  Future<void> _queueScan() async {
    setState(() {
      _message = null;
      _error = null;
    });
    try {
      final response = await _apiClient.queueAutoIngestionScan();
      if (!mounted) return;
      setState(() => _message = 'Queued automatic ingestion scan job ${response['id'] ?? ''}.');
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = '$error');
    }
  }

  Future<void> _saveDocumentClassificationConfig(Map<String, dynamic> config) async {
    setState(() {
      _saving = true;
      _message = null;
      _error = null;
    });
    try {
      final response = await _apiClient.updateDocumentClassificationSettings(config);
      if (!mounted) return;
      setState(() {
        _message = 'Updated ${(response['document_types'] as List<dynamic>? ?? <dynamic>[]).length} document type mapping(s).';
        _saving = false;
        _reload();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _saving = false;
      });
    }
  }

  void _recordChange(String key, dynamic value) {
    setState(() => _pendingUpdates[key] = value);
  }

  @override
  Widget build(BuildContext context) {
    final isAdmin = AuthController.instance.isAdmin;
    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Settings', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                const Text('Manage configuration by section. Search context is selected on the Search & Query page rather than being changed globally here.'),
              ]),
            ),
            OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            const SizedBox(width: 12),
            FilledButton.icon(
              onPressed: !isAdmin || _saving || _pendingUpdates.isEmpty ? null : _save,
              icon: _saving ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save_outlined),
              label: Text(_pendingUpdates.isEmpty ? 'No changes' : 'Save ${_pendingUpdates.length} change(s)'),
            ),
          ]),
          const SizedBox(height: 16),
          if (_message != null) _Banner(message: _message!, positive: true),
          if (_error != null) _Banner(message: _error!, positive: false),
          if (!isAdmin) const _Banner(message: 'Admin role required to update settings. Current values are read-only.', positive: false),
          const SizedBox(height: 16),
          _SettingsMenu(selected: _section, onSelected: (section) => setState(() => _section = section)),
          const SizedBox(height: 16),
          _buildSection(isAdmin),
        ]),
      ),
    );
  }

  Widget _buildSection(bool isAdmin) {
    final editable = isAdmin && !_saving;
    switch (_section) {
      case _SettingsSection.queryVocabulary:
        return _SectionShell(
          title: 'Query vocabulary',
          description: 'Edit static industry vocabularies, aliases and requirement groups. Search-time industry selection now lives on the Search & Query page.',
          child: IndustryPackEditorCard(editable: editable),
        );
      case _SettingsSection.completenessRules:
        return _SectionShell(title: 'Completeness rulesets', description: 'Industry-specific mandatory evidence and completeness rules.', child: IndustryRulesetSettingsCard(editable: editable));
      case _SettingsSection.demoArchives:
        return _SectionShell(title: 'Demo archives', description: 'Generate and manage industry-specific demonstration archives.', child: DemoArchiveSettingsCard(editable: editable));
      case _SettingsSection.documentClassification:
        return _SectionShell(title: 'Document classification', description: 'Document Type to Category mappings used for filename-based and manual categorisation.', child: _DocumentClassificationCard(future: _documentClassificationFuture, editable: editable, onSave: _saveDocumentClassificationConfig));
      case _SettingsSection.ingestion:
        return _SectionShell(title: 'Ingestion', description: 'Source-folder ingestion status and scan controls.', child: _AutoIngestionStatusCard(future: _autoIngestionFuture, onScanNow: isAdmin ? _scanNow : null, onQueueScan: isAdmin ? _queueScan : null));
      case _SettingsSection.runtime:
        return _SectionShell(title: 'Runtime settings', description: 'Safe runtime settings. Secrets remain environment or secret-manager controlled.', child: _RuntimeSettings(future: _settingsFuture, pendingUpdates: _pendingUpdates, editable: isAdmin, onChanged: _recordChange));
    }
  }
}

enum _SettingsSection { queryVocabulary, completenessRules, demoArchives, documentClassification, ingestion, runtime }

class _SettingsMenu extends StatelessWidget {
  const _SettingsMenu({required this.selected, required this.onSelected});
  final _SettingsSection selected;
  final ValueChanged<_SettingsSection> onSelected;

  @override
  Widget build(BuildContext context) {
    final items = <_SettingsMenuItem>[
      _SettingsMenuItem(_SettingsSection.queryVocabulary, 'Query vocabulary', Icons.manage_search_outlined),
      _SettingsMenuItem(_SettingsSection.completenessRules, 'Completeness rules', Icons.rule_folder_outlined),
      _SettingsMenuItem(_SettingsSection.demoArchives, 'Demo archives', Icons.inventory_2_outlined),
      _SettingsMenuItem(_SettingsSection.documentClassification, 'Document classification', Icons.category_outlined),
      _SettingsMenuItem(_SettingsSection.ingestion, 'Ingestion', Icons.cloud_upload_outlined),
      _SettingsMenuItem(_SettingsSection.runtime, 'Runtime', Icons.tune_outlined),
    ];
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: items
          .map((item) => ChoiceChip(
                avatar: Icon(item.icon, size: 18),
                label: Text(item.label),
                selected: selected == item.section,
                onSelected: (_) => onSelected(item.section),
              ))
          .toList(),
    );
  }
}

class _SettingsMenuItem {
  const _SettingsMenuItem(this.section, this.label, this.icon);
  final _SettingsSection section;
  final String label;
  final IconData icon;
}

class _SectionShell extends StatelessWidget {
  const _SectionShell({required this.title, required this.description, required this.child});
  final String title;
  final String description;
  final Widget child;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Text(description),
              ])),
            ]),
          ),
        ),
        const SizedBox(height: 12),
        child,
      ]);
}

class _RuntimeSettings extends StatelessWidget {
  const _RuntimeSettings({required this.future, required this.pendingUpdates, required this.editable, required this.onChanged});
  final Future<Map<String, dynamic>> future;
  final Map<String, dynamic> pendingUpdates;
  final bool editable;
  final void Function(String key, dynamic value) onChanged;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const Center(child: Padding(padding: EdgeInsets.all(48), child: CircularProgressIndicator()));
        if (snapshot.hasError) return Center(child: Text('Unable to load settings: ${snapshot.error}'));
        final categories = (snapshot.data?['categories'] as Map<String, dynamic>? ?? <String, dynamic>{});
        if (categories.isEmpty) return const Center(child: Text('No settings returned by API.'));
        return Column(
          children: categories.entries.map((entry) {
            final items = (entry.value as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().where((item) => item['key'] != 'client_industry').toList();
            if (items.isEmpty) return const SizedBox.shrink();
            return _SettingsCategoryCard(category: entry.key, items: items, pendingUpdates: pendingUpdates, editable: editable, onChanged: onChanged);
          }).toList(),
        );
      },
    );
  }
}

class _DocumentClassificationCard extends StatelessWidget {
  const _DocumentClassificationCard({required this.future, required this.editable, required this.onSave});

  final Future<Map<String, dynamic>> future;
  final bool editable;
  final Future<void> Function(Map<String, dynamic> config) onSave;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: FutureBuilder<Map<String, dynamic>>(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
            if (snapshot.hasError) return Text('Document classification settings unavailable: ${snapshot.error}');
            final config = (snapshot.data?['config'] as Map<String, dynamic>? ?? <String, dynamic>{});
            final documentTypes = (snapshot.data?['document_types'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Document classification', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  const Text('Document Types are mapped to Categories. Filename patterns are used during ingestion before manual categorisation.'),
                ])),
                OutlinedButton.icon(onPressed: editable ? () => _showAddMappingDialog(context, config, documentTypes) : null, icon: const Icon(Icons.add), label: const Text('Add mapping')),
              ]),
              const SizedBox(height: 12),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  columns: const [DataColumn(label: Text('Document Type')), DataColumn(label: Text('Category')), DataColumn(label: Text('Filename patterns'))],
                  rows: documentTypes.map((item) {
                    final patterns = (item['filename_patterns'] as List<dynamic>? ?? <dynamic>[]).join(', ');
                    return DataRow(cells: [
                      DataCell(Text('${item['document_type'] ?? ''}')),
                      DataCell(Text('${item['category'] ?? ''}')),
                      DataCell(SizedBox(width: 520, child: Text(patterns, overflow: TextOverflow.ellipsis))),
                    ]);
                  }).toList(),
                ),
              ),
            ]);
          },
        ),
      ),
    );
  }

  Future<void> _showAddMappingDialog(BuildContext context, Map<String, dynamic> config, List<Map<String, dynamic>> documentTypes) async {
    final documentTypeController = TextEditingController();
    final categoryController = TextEditingController();
    final patternsController = TextEditingController();
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add document type mapping'),
        content: SizedBox(
          width: 520,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: documentTypeController, decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Document Type')),
            const SizedBox(height: 12),
            TextField(controller: categoryController, decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Category')),
            const SizedBox(height: 12),
            TextField(controller: patternsController, decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Filename patterns, comma separated')),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              if (documentTypeController.text.trim().isEmpty || categoryController.text.trim().isEmpty) return;
              Navigator.of(context).pop(<String, dynamic>{
                'document_type': documentTypeController.text.trim(),
                'category': categoryController.text.trim(),
                'filename_patterns': patternsController.text.split(',').map((value) => value.trim()).where((value) => value.isNotEmpty).toList(),
              });
            },
            child: const Text('Add'),
          ),
        ],
      ),
    );
    documentTypeController.dispose();
    categoryController.dispose();
    patternsController.dispose();
    if (result == null) return;
    final nextConfig = Map<String, dynamic>.from(config);
    nextConfig['document_types'] = <Map<String, dynamic>>[...documentTypes, result];
    await onSave(nextConfig);
  }
}

class _AutoIngestionStatusCard extends StatelessWidget {
  const _AutoIngestionStatusCard({required this.future, required this.onScanNow, required this.onQueueScan});

  final Future<Map<String, dynamic>> future;
  final VoidCallback? onScanNow;
  final VoidCallback? onQueueScan;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: FutureBuilder<Map<String, dynamic>>(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
            if (snapshot.hasError) return Text('Automatic ingestion status unavailable: ${snapshot.error}');
            final data = snapshot.data ?? <String, dynamic>{};
            final folders = (data['folders'] as Map<String, dynamic>? ?? <String, dynamic>{});
            final folderState = (data['folder_state'] as Map<String, dynamic>? ?? <String, dynamic>{});
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Automatic source-folder ingestion', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    Chip(label: Text('Enabled: ${data['enabled']}')),
                    Chip(label: Text('Poll: ${data['poll_seconds']}s')),
                    Chip(label: Text('Strict structure: ${data['strict_structure']}')),
                  ]),
                ])),
                OutlinedButton.icon(onPressed: onQueueScan, icon: const Icon(Icons.schedule), label: const Text('Queue scan job')),
                const SizedBox(width: 8),
                FilledButton.icon(onPressed: onScanNow, icon: const Icon(Icons.play_arrow), label: const Text('Scan now')),
              ]),
              const SizedBox(height: 12),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: folders.entries.map((entry) {
                  final state = folderState[entry.key] as Map<String, dynamic>? ?? <String, dynamic>{};
                  return Container(
                    width: 330,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(_label(entry.key), style: const TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 4),
                      SelectableText('${entry.value}', maxLines: 2),
                      const SizedBox(height: 4),
                      Text('Exists: ${state['exists'] ?? false} · ZIPs: ${state['zip_count'] ?? 0}', style: Theme.of(context).textTheme.bodySmall),
                    ]),
                  );
                }).toList(),
              ),
            ]);
          },
        ),
      ),
    );
  }
}

class _SettingsCategoryCard extends StatelessWidget {
  const _SettingsCategoryCard({required this.category, required this.items, required this.pendingUpdates, required this.editable, required this.onChanged});
  final String category;
  final List<Map<String, dynamic>> items;
  final Map<String, dynamic> pendingUpdates;
  final bool editable;
  final void Function(String key, dynamic value) onChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(category, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          ...items.map((item) => _SettingRow(item: item, pendingValue: pendingUpdates[item['key']], editable: editable, onChanged: onChanged)),
        ]),
      ),
    );
  }
}

class _SettingRow extends StatefulWidget {
  const _SettingRow({required this.item, required this.pendingValue, required this.editable, required this.onChanged});
  final Map<String, dynamic> item;
  final dynamic pendingValue;
  final bool editable;
  final void Function(String key, dynamic value) onChanged;

  @override
  State<_SettingRow> createState() => _SettingRowState();
}

class _SettingRowState extends State<_SettingRow> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: '${widget.pendingValue ?? widget.item['value'] ?? ''}');
  }

  @override
  void didUpdateWidget(covariant _SettingRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    final nextText = '${widget.pendingValue ?? widget.item['value'] ?? ''}';
    if (_controller.text != nextText && widget.pendingValue == null) _controller.text = nextText;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final keyName = '${widget.item['key']}';
    final valueType = '${widget.item['value_type']}';
    final canEdit = widget.editable && widget.item['editable'] == true && widget.item['secret'] != true;
    final hasPending = widget.pendingValue != null;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
          width: 280,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(keyName, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text('${widget.item['description'] ?? ''}', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 4),
            Wrap(spacing: 6, children: [
              Chip(label: Text('${widget.item['source']}'), visualDensity: VisualDensity.compact),
              if (widget.item['secret'] == true) const Chip(label: Text('secret'), visualDensity: VisualDensity.compact),
              if (!canEdit) const Chip(label: Text('read-only'), visualDensity: VisualDensity.compact),
              if (hasPending) const Chip(label: Text('changed'), visualDensity: VisualDensity.compact),
            ]),
          ]),
        ),
        const SizedBox(width: 16),
        Expanded(child: _editorFor(keyName, valueType, canEdit)),
      ]),
    );
  }

  Widget _editorFor(String keyName, String valueType, bool canEdit) {
    if (valueType == 'bool') {
      final current = widget.pendingValue is bool ? widget.pendingValue as bool : '${widget.item['value']}'.toLowerCase() == 'true';
      return Align(alignment: Alignment.centerLeft, child: Switch(value: current, onChanged: canEdit ? (value) => widget.onChanged(keyName, value) : null));
    }
    return TextField(
      controller: _controller,
      enabled: canEdit,
      decoration: InputDecoration(border: const OutlineInputBorder(), labelText: valueType == 'int' ? 'Integer value' : 'Value'),
      keyboardType: valueType == 'int' ? TextInputType.number : TextInputType.text,
      onChanged: (value) => widget.onChanged(keyName, valueType == 'int' ? int.tryParse(value) ?? value : value),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.message, required this.positive});
  final String message;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: positive ? scheme.primaryContainer : scheme.errorContainer, borderRadius: BorderRadius.circular(12)),
      child: Text(message, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
    );
  }
}

String _label(String value) => value.replaceAll('_', ' ').split(' ').map((part) => part.isEmpty ? part : part.substring(0, 1).toUpperCase() + part.substring(1)).join(' ');
