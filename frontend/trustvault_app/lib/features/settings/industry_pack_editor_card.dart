import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/auth/auth_controller.dart';

class IndustryPackEditorCard extends StatefulWidget {
  const IndustryPackEditorCard({super.key, required this.editable});

  final bool editable;

  @override
  State<IndustryPackEditorCard> createState() => _IndustryPackEditorCardState();
}

class _IndustryPackEditorCardState extends State<IndustryPackEditorCard> {
  final _api = _IndustryPackEditorApi();
  late Future<Map<String, dynamic>> _future;
  bool _saving = false;
  String? _message;
  String? _error;

  @override
  void initState() {
    super.initState();
    _future = _api.getActiveIndustryPack();
  }

  void _reload() {
    setState(() {
      _message = null;
      _error = null;
      _future = _api.getActiveIndustryPack();
    });
  }

  Future<void> _editPack(Map<String, dynamic> pack) async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _IndustryPackJsonDialog(pack: pack),
    );
    if (result == null) return;
    setState(() {
      _saving = true;
      _message = null;
      _error = null;
    });
    try {
      await _api.updateIndustryPack('${result['key'] ?? pack['key']}', result);
      if (!mounted) return;
      setState(() {
        _message = 'Static query data override saved for ${result['label'] ?? result['key'] ?? 'industry pack'}.';
        _saving = false;
        _future = _api.getActiveIndustryPack();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _saving = false;
      });
    }
  }

  Future<void> _resetPack(Map<String, dynamic> pack) async {
    final key = '${pack['key']}';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset static query data'),
        content: Text('Remove the custom override for ${pack['label'] ?? key} and restore the shipped default pack?'),
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
      await _api.resetIndustryPack(key);
      if (!mounted) return;
      setState(() {
        _message = 'Static query data reset for ${pack['label'] ?? key}.';
        _saving = false;
        _future = _api.getActiveIndustryPack();
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
            if (snapshot.hasError) return Text('Static query data editor unavailable: ${snapshot.error}');
            final pack = snapshot.data ?? <String, dynamic>{};
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Amend static query data', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text('Edit the active industry pack as JSON. Saved changes are stored as a database override over the shipped ${pack['label'] ?? 'industry'} defaults.'),
                ])),
                OutlinedButton.icon(onPressed: _reload, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
              ]),
              const SizedBox(height: 10),
              if (_message != null) _InlineBanner(message: _message!, positive: true),
              if (_error != null) _InlineBanner(message: _error!, positive: false),
              Wrap(spacing: 8, runSpacing: 8, children: [
                Chip(label: Text('Active: ${pack['label'] ?? pack['key'] ?? '-'}')),
                if (pack['customised'] == true) const Chip(label: Text('Custom override active')),
                Chip(label: Text('${(pack['vocabulary_lists'] as List<dynamic>? ?? <dynamic>[]).length} vocabulary list(s)')),
                Chip(label: Text('${(pack['requirement_groups'] as List<dynamic>? ?? <dynamic>[]).length} requirement group(s)')),
              ]),
              const SizedBox(height: 12),
              Wrap(spacing: 8, runSpacing: 8, children: [
                FilledButton.icon(onPressed: widget.editable && !_saving ? () => _editPack(pack) : null, icon: const Icon(Icons.edit_outlined), label: const Text('Edit static data JSON')),
                OutlinedButton.icon(onPressed: widget.editable && !_saving && pack['customised'] == true ? () => _resetPack(pack) : null, icon: const Icon(Icons.restore), label: const Text('Reset to default')),
              ]),
            ]);
          },
        ),
      ),
    );
  }
}

class _IndustryPackJsonDialog extends StatefulWidget {
  const _IndustryPackJsonDialog({required this.pack});

  final Map<String, dynamic> pack;

  @override
  State<_IndustryPackJsonDialog> createState() => _IndustryPackJsonDialogState();
}

class _IndustryPackJsonDialogState extends State<_IndustryPackJsonDialog> {
  late final TextEditingController _controller;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: const JsonEncoder.withIndent('  ').convert(widget.pack));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit static query data JSON'),
      content: SizedBox(
        width: 900,
        height: 620,
        child: Column(children: [
          const Text('Amend entity terms, vocabulary lists, aliases, field bindings and requirement groups.'),
          const SizedBox(height: 12),
          if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          Expanded(
            child: TextField(
              controller: _controller,
              expands: true,
              maxLines: null,
              minLines: null,
              decoration: const InputDecoration(border: OutlineInputBorder(), labelText: 'Industry pack JSON'),
              style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
            ),
          ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
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
          },
          child: const Text('Save'),
        ),
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
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: positive ? scheme.primaryContainer : scheme.errorContainer, borderRadius: BorderRadius.circular(12)),
      child: Text(message, style: TextStyle(color: positive ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
    );
  }
}

class _IndustryPackEditorApi {
  _IndustryPackEditorApi()
      : _dio = Dio(BaseOptions(baseUrl: const String.fromEnvironment('TRUSTVAULT_API_BASE_URL', defaultValue: 'http://localhost:8000'), connectTimeout: const Duration(seconds: 10), receiveTimeout: const Duration(seconds: 60))) {
    _dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      final token = AuthController.instance.accessToken;
      if (token != null && token.isNotEmpty) options.headers['Authorization'] = 'Bearer $token';
      handler.next(options);
    }));
  }

  final Dio _dio;

  Future<Map<String, dynamic>> getActiveIndustryPack() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/settings/industry-packs/active');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateIndustryPack(String industryKey, Map<String, dynamic> pack) async {
    final response = await _dio.put<Map<String, dynamic>>('/api/v1/settings/industry-packs/$industryKey', data: <String, dynamic>{'pack': pack});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> resetIndustryPack(String industryKey) async {
    final response = await _dio.delete<Map<String, dynamic>>('/api/v1/settings/industry-packs/$industryKey/override');
    return response.data ?? <String, dynamic>{};
  }
}
