import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/auth/auth_controller.dart';

class DemoArchiveSettingsCard extends StatefulWidget {
  const DemoArchiveSettingsCard({super.key, required this.editable});

  final bool editable;

  @override
  State<DemoArchiveSettingsCard> createState() => _DemoArchiveSettingsCardState();
}

class _DemoArchiveSettingsCardState extends State<DemoArchiveSettingsCard> {
  final _api = _DemoArchiveApi();
  late Future<List<Map<String, dynamic>>> _future;
  bool _generating = false;
  String? _message;
  String? _error;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Map<String, dynamic>>> _load() async {
    final response = await _api.getDemoArchives();
    return (response['archives'] as List<dynamic>? ?? <dynamic>[]).whereType<Map<String, dynamic>>().toList();
  }

  void _reload() {
    setState(() {
      _message = null;
      _error = null;
      _future = _load();
    });
  }

  Future<void> _generate(Map<String, dynamic> archive) async {
    setState(() {
      _generating = true;
      _message = null;
      _error = null;
    });
    try {
      final response = await _api.generateDemoArchive('${archive['key']}');
      if (!mounted) return;
      setState(() {
        _message = 'Generated ${response['entity_count'] ?? 0} entity archive(s) for ${archive['label'] ?? archive['key']}.';
        _generating = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _generating = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: FutureBuilder<List<Map<String, dynamic>>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const LinearProgressIndicator();
            if (snapshot.hasError) return Text('Demo archive controls unavailable: ${snapshot.error}');
            final archives = snapshot.data ?? <Map<String, dynamic>>[];
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Demo archives', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  const Text('Generate additional Healthcare and Supplier Due Diligence evidence archives. Generated archives are ingested, rebuilt as FITS and indexed for query demonstrations.'),
                ])),
                OutlinedButton.icon(onPressed: _reload, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
              ]),
              const SizedBox(height: 10),
              if (_message != null) _InlineBanner(message: _message!, positive: true),
              if (_error != null) _InlineBanner(message: _error!, positive: false),
              if (archives.isEmpty)
                const Text('No demo archives are available from the API.')
              else
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: archives.map((archive) {
                    return Container(
                      width: 360,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${archive['label'] ?? archive['key']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 6),
                        Text('${archive['description'] ?? ''}', maxLines: 3, overflow: TextOverflow.ellipsis),
                        const SizedBox(height: 8),
                        Chip(label: Text('${archive['entity_count'] ?? 0} entities')),
                        const SizedBox(height: 8),
                        FilledButton.icon(onPressed: widget.editable && !_generating ? () => _generate(archive) : null, icon: const Icon(Icons.archive_outlined), label: const Text('Generate archive')),
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

class _DemoArchiveApi {
  _DemoArchiveApi()
      : _dio = Dio(BaseOptions(baseUrl: const String.fromEnvironment('TRUSTVAULT_API_BASE_URL', defaultValue: 'http://localhost:8000'), connectTimeout: const Duration(seconds: 10), receiveTimeout: const Duration(seconds: 60))) {
    _dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
      final token = AuthController.instance.accessToken;
      if (token != null && token.isNotEmpty) options.headers['Authorization'] = 'Bearer $token';
      handler.next(options);
    }));
  }

  final Dio _dio;

  Future<Map<String, dynamic>> getDemoArchives() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/demo-archives');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> generateDemoArchive(String archiveKey) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/demo-archives/$archiveKey/generate');
    return response.data ?? <String, dynamic>{};
  }
}
