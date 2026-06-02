import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/auth/auth_controller.dart';

class IndustryPackSettingsCard extends StatefulWidget {
  const IndustryPackSettingsCard({super.key, required this.editable});

  final bool editable;

  @override
  State<IndustryPackSettingsCard> createState() => _IndustryPackSettingsCardState();
}

class _IndustryPackSettingsCardState extends State<IndustryPackSettingsCard> {
  final _api = _IndustryPackApi();
  late Future<_IndustryPackSettingsData> _future;
  String? _selectedIndustry;
  bool _saving = false;
  String? _message;
  String? _error;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_IndustryPackSettingsData> _load() async {
    final results = await Future.wait<Map<String, dynamic>>([
      _api.getIndustryPacks(),
      _api.getActiveIndustryPack(),
    ]);
    final packsResponse = results[0];
    final activePack = results[1];
    final packs = (packsResponse['industry_packs'] as List<dynamic>? ?? <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .toList();
    final activeKey = '${packsResponse['active_industry'] ?? activePack['key'] ?? 'financial_services'}';
    _selectedIndustry ??= activeKey;
    return _IndustryPackSettingsData(packs: packs, activePack: activePack, activeIndustry: activeKey);
  }

  void _reload() {
    setState(() {
      _message = null;
      _error = null;
      _future = _load();
    });
  }

  Future<void> _saveIndustry() async {
    final selected = _selectedIndustry;
    if (selected == null || selected.isEmpty) return;
    setState(() {
      _saving = true;
      _message = null;
      _error = null;
    });
    try {
      await _api.updateClientIndustry(selected);
      final nextPack = await _api.getIndustryPack(selected);
      if (!mounted) return;
      setState(() {
        _message = 'Client industry updated to ${nextPack['label'] ?? selected}.';
        _saving = false;
        _future = _load();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _saving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: FutureBuilder<_IndustryPackSettingsData>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
            if (snapshot.hasError) return Text('Industry pack settings unavailable: ${snapshot.error}');
            final data = snapshot.data!;
            final selected = _selectedIndustry ?? data.activeIndustry;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Client industry and static query data', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 6),
                          const Text('Select the industry pack used by the query vocabulary resolver. The active pack defines entity terms, filter dimensions, aliases, document types and requirement groups.'),
                        ],
                      ),
                    ),
                    OutlinedButton.icon(onPressed: _reload, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
                  ],
                ),
                const SizedBox(height: 12),
                if (_message != null) _InlineBanner(message: _message!, positive: true),
                if (_error != null) _InlineBanner(message: _error!, positive: false),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    SizedBox(
                      width: 420,
                      child: DropdownButtonFormField<String>(
                        value: selected,
                        decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Client industry'),
                        items: data.packs.map((pack) => DropdownMenuItem<String>(value: '${pack['key']}', child: Text('${pack['label']}'))).toList(),
                        onChanged: widget.editable && !_saving ? (value) => setState(() => _selectedIndustry = value) : null,
                      ),
                    ),
                    FilledButton.icon(
                      onPressed: widget.editable && !_saving && selected != data.activeIndustry ? _saveIndustry : null,
                      icon: _saving ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save_outlined),
                      label: const Text('Apply industry'),
                    ),
                    Chip(label: Text('Active: ${data.activePack['label'] ?? data.activeIndustry}')),
                  ],
                ),
                const SizedBox(height: 16),
                _ActiveIndustrySummary(pack: data.activePack),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ActiveIndustrySummary extends StatelessWidget {
  const _ActiveIndustrySummary({required this.pack});

  final Map<String, dynamic> pack;

  @override
  Widget build(BuildContext context) {
    final entityTerms = (pack['entity_type_terms'] as List<dynamic>? ?? <dynamic>[]).map((item) => '$item').toList();
    final vocabularyLists = (pack['vocabulary_lists'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
    final requirementGroups = (pack['requirement_groups'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${pack['label'] ?? 'Active industry'} static data', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Text('${pack['description'] ?? ''}'),
        const SizedBox(height: 12),
        _WrapSection(title: 'Entity terms', values: entityTerms),
        const SizedBox(height: 12),
        _VocabularyListsTable(vocabularyLists: vocabularyLists),
        const SizedBox(height: 12),
        _RequirementGroupsTable(requirementGroups: requirementGroups),
      ],
    );
  }
}

class _WrapSection extends StatelessWidget {
  const _WrapSection({required this.title, required this.values});

  final String title;
  final List<String> values;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      Wrap(spacing: 8, runSpacing: 8, children: values.map((value) => Chip(label: Text(value))).toList()),
    ]);
  }
}

class _VocabularyListsTable extends StatelessWidget {
  const _VocabularyListsTable({required this.vocabularyLists});

  final List<Map<String, dynamic>> vocabularyLists;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Vocabulary lists', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          columns: const [
            DataColumn(label: Text('List')),
            DataColumn(label: Text('Field binding')),
            DataColumn(label: Text('Use')),
            DataColumn(label: Text('Values and aliases')),
          ],
          rows: vocabularyLists.map((list) {
            final items = (list['items'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().map((item) {
              final aliases = (item['aliases'] as List<dynamic>? ?? <dynamic>[]).join(', ');
              return aliases.isEmpty ? '${item['canonical_value']}' : '${item['canonical_value']} ($aliases)';
            }).join(' · ');
            return DataRow(cells: [
              DataCell(Text('${list['label'] ?? list['list_key']}')),
              DataCell(Text('${list['field_binding'] ?? '-'}')),
              DataCell(Text(list['is_requirement_dimension'] == true ? 'Requirement' : 'Filter')),
              DataCell(SizedBox(width: 760, child: Text(items, overflow: TextOverflow.ellipsis))),
            ]);
          }).toList(),
        ),
      ),
    ]);
  }
}

class _RequirementGroupsTable extends StatelessWidget {
  const _RequirementGroupsTable({required this.requirementGroups});

  final List<Map<String, dynamic>> requirementGroups;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Requirement groups', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          columns: const [
            DataColumn(label: Text('Group')),
            DataColumn(label: Text('Aliases')),
            DataColumn(label: Text('Default document types')),
          ],
          rows: requirementGroups.map((group) => DataRow(cells: [
                DataCell(Text('${group['label'] ?? group['key']}')),
                DataCell(SizedBox(width: 360, child: Text((group['aliases'] as List<dynamic>? ?? <dynamic>[]).join(', '), overflow: TextOverflow.ellipsis))),
                DataCell(SizedBox(width: 420, child: Text((group['default_document_types'] as List<dynamic>? ?? <dynamic>[]).join(', '), overflow: TextOverflow.ellipsis))),
              ])).toList(),
        ),
      ),
    ]);
  }
}

class _InlineBanner extends StatelessWidget {
  const _InlineBanner({required this.message, required this.positive});

  final String message;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: positive ? scheme.primaryContainer : scheme.errorContainer, borderRadius: BorderRadius.circular(12)),
      child: Text(message, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
    );
  }
}

class _IndustryPackSettingsData {
  const _IndustryPackSettingsData({required this.packs, required this.activePack, required this.activeIndustry});

  final List<Map<String, dynamic>> packs;
  final Map<String, dynamic> activePack;
  final String activeIndustry;
}

class _IndustryPackApi {
  _IndustryPackApi()
      : _dio = Dio(BaseOptions(
          baseUrl: const String.fromEnvironment('TRUSTVAULT_API_BASE_URL', defaultValue: 'http://localhost:8000'),
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 60),
        )) {
    _dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      final token = AuthController.instance.accessToken;
      if (token != null && token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    }));
  }

  final Dio _dio;

  Future<Map<String, dynamic>> getIndustryPacks() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/settings/industry-packs');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getActiveIndustryPack() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/settings/industry-packs/active');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getIndustryPack(String industryKey) async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/settings/industry-packs/$industryKey');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateClientIndustry(String industryKey) async {
    final response = await _dio.patch<Map<String, dynamic>>('/api/v1/settings', data: <String, dynamic>{'updates': <String, dynamic>{'client_industry': industryKey}});
    return response.data ?? <String, dynamic>{};
  }
}
