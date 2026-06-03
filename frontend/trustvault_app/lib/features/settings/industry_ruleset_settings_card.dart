import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/auth/auth_controller.dart';

class IndustryRulesetSettingsCard extends StatefulWidget {
  const IndustryRulesetSettingsCard({super.key, required this.editable});

  final bool editable;

  @override
  State<IndustryRulesetSettingsCard> createState() => _IndustryRulesetSettingsCardState();
}

class _IndustryRulesetSettingsCardState extends State<IndustryRulesetSettingsCard> {
  final _api = _IndustryRulesetApi();
  late Future<Map<String, dynamic>> _future;
  bool _saving = false;
  String? _message;
  String? _error;

  @override
  void initState() {
    super.initState();
    _future = _api.getIndustryRulesets();
  }

  void _reload() {
    setState(() {
      _message = null;
      _error = null;
      _future = _api.getIndustryRulesets();
    });
  }

  Future<void> _editRuleset(Map<String, dynamic> ruleset) async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _RulesetJsonDialog(ruleset: ruleset),
    );
    if (result == null) return;
    setState(() {
      _saving = true;
      _message = null;
      _error = null;
    });
    try {
      final industryKey = '${result['industry_key'] ?? ruleset['industry_key']}';
      await _api.updateIndustryRuleset(industryKey, result);
      if (!mounted) return;
      setState(() {
        _message = 'Completeness ruleset saved for ${result['name'] ?? industryKey}.';
        _saving = false;
        _future = _api.getIndustryRulesets();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _saving = false;
      });
    }
  }

  Future<void> _resetRuleset(Map<String, dynamic> ruleset) async {
    final industryKey = '${ruleset['industry_key']}';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset completeness ruleset'),
        content: Text('Reset ${ruleset['name'] ?? industryKey} to the shipped default rules?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Reset')),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() {
      _saving = true;
      _message = null;
      _error = null;
    });
    try {
      await _api.resetIndustryRuleset(industryKey);
      if (!mounted) return;
      setState(() {
        _message = 'Completeness ruleset reset for $industryKey.';
        _saving = false;
        _future = _api.getIndustryRulesets();
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
        child: FutureBuilder<Map<String, dynamic>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
            if (snapshot.hasError) return Text('Industry completeness rulesets unavailable: ${snapshot.error}');
            final response = snapshot.data ?? <String, dynamic>{};
            final activeIndustry = '${response['active_industry'] ?? ''}';
            final rulesets = (response['industry_rulesets'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Industry completeness rulesets', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  const Text('Edit the required evidence rules used by completeness checks for each industry. These are separate from the query vocabulary.'),
                ])),
                OutlinedButton.icon(onPressed: _reload, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
              ]),
              const SizedBox(height: 10),
              if (_message != null) _InlineBanner(message: _message!, positive: true),
              if (_error != null) _InlineBanner(message: _error!, positive: false),
              if (rulesets.isEmpty)
                const Text('No industry completeness rulesets returned by the API.')
              else
                Wrap(spacing: 12, runSpacing: 12, children: rulesets.map((ruleset) {
                  final isActive = '${ruleset['industry_key']}' == activeIndustry;
                  final rules = (ruleset['rules'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
                  return Container(
                    width: 410,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(border: Border.all(color: isActive ? Theme.of(context).colorScheme.primary : Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Expanded(child: Text('${ruleset['name'] ?? ruleset['industry_key']}', style: const TextStyle(fontWeight: FontWeight.w700))),
                        if (isActive) const Chip(label: Text('Active')),
                        if (ruleset['customised'] == true) const Chip(label: Text('Custom')),
                      ]),
                      const SizedBox(height: 6),
                      Text('${ruleset['description'] ?? ''}', maxLines: 2, overflow: TextOverflow.ellipsis),
                      const SizedBox(height: 8),
                      Wrap(spacing: 8, children: [
                        Chip(label: Text('${rules.length} rule(s)')),
                        Chip(label: Text('${rules.where((rule) => rule['required'] == true).length} required')),
                      ]),
                      const SizedBox(height: 8),
                      Text(rules.map((rule) => '${rule['document_type']}').take(5).join(', '), maxLines: 2, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
                      const SizedBox(height: 10),
                      Wrap(spacing: 8, children: [
                        FilledButton.icon(onPressed: widget.editable && !_saving ? () => _editRuleset(ruleset) : null, icon: const Icon(Icons.edit_outlined), label: const Text('Edit JSON')),
                        OutlinedButton.icon(onPressed: widget.editable && !_saving && ruleset['customised'] == true ? () => _resetRuleset(ruleset) : null, icon: const Icon(Icons.restore), label: const Text('Reset')),
                      ]),
                    ]),
                  );
                }).toList()),
            ]);
          },
        ),
      ),
    );
  }
}

class _RulesetJsonDialog extends StatefulWidget {
  const _RulesetJsonDialog({required this.ruleset});

  final Map<String, dynamic> ruleset;

  @override
  State<_RulesetJsonDialog> createState() => _RulesetJsonDialogState();
}

class _RulesetJsonDialogState extends State<_RulesetJsonDialog> {
  late final TextEditingController _controller;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: const JsonEncoder.withIndent('  ').convert(widget.ruleset));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit completeness ruleset JSON'),
      content: SizedBox(
        width: 900,
        height: 620,
        child: Column(children: [
          const Text('Amend required evidence rules, applicable entity types and metadata filters.'),
          const SizedBox(height: 12),
          if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          Expanded(child: TextField(controller: _controller, expands: true, maxLines: null, minLines: null, decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Ruleset JSON'), style: const TextStyle(fontFamily: 'monospace', fontSize: 13))),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(onPressed: () {
          try {
            final decoded = jsonDecode(_controller.text);
            if (decoded is! Map<String, dynamic>) {
              setState(() => _error = 'JSON must be an object.');
              return;
            }
            Navigator.of(context).pop(decoded);
          } catch (error) {
            setState(() => _error = 'Invalid JSON: $error');
          }
        }, child: const Text('Save')),
      ],
    );
  }
}

class _InlineBanner extends StatelessWidget {
  const _InlineBanner({required this.message, required this.positive});

  final String message;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(width: double.infinity, margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: positive ? scheme.primaryContainer : scheme.errorContainer, borderRadius: BorderRadius.circular(12)), child: Text(message, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)));
  }
}

class _IndustryRulesetApi {
  _IndustryRulesetApi()
      : _dio = Dio(BaseOptions(baseUrl: const String.fromEnvironment('TRUSTVAULT_API_BASE_URL', defaultValue: 'http://localhost:8000'), connectTimeout: const Duration(seconds: 10), receiveTimeout: const Duration(seconds: 60))) {
    _dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      final token = AuthController.instance.accessToken;
      if (token != null && token.isNotEmpty) options.headers['Authorization'] = 'Bearer $token';
      handler.next(options);
    }));
  }

  final Dio _dio;

  Future<Map<String, dynamic>> getIndustryRulesets() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/settings/industry-rulesets');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateIndustryRuleset(String industryKey, Map<String, dynamic> ruleset) async {
    final response = await _dio.put<Map<String, dynamic>>('/api/v1/settings/industry-rulesets/$industryKey', data: <String, dynamic>{'ruleset': ruleset});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> resetIndustryRuleset(String industryKey) async {
    final response = await _dio.delete<Map<String, dynamic>>('/api/v1/settings/industry-rulesets/$industryKey/override');
    return response.data ?? <String, dynamic>{};
  }
}
