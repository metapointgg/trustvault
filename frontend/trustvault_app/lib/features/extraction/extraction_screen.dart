import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/customer_selector_card.dart';
import '../../shared/selected_customer.dart';

class ExtractionScreen extends StatefulWidget {
  const ExtractionScreen({super.key});

  @override
  State<ExtractionScreen> createState() => _ExtractionScreenState();
}

class _ExtractionScreenState extends State<ExtractionScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  Future<Map<String, dynamic>>? _future;
  String? _loadedFor;

  @override
  void initState() {
    super.initState();
    SelectedCustomerController.selected.addListener(_load);
    _load();
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_load);
    super.dispose();
  }

  void _load() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId == null || externalId.isEmpty) {
      setState(() {
        _future = null;
        _loadedFor = null;
      });
      return;
    }
    final nextFuture = _apiClient.getExtractionReport(externalId);
    setState(() {
      _future = nextFuture;
      _loadedFor = externalId;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Header(title: 'Extraction', subtitle: 'OCR/search text, extracted fields and extraction events read from one customer FITS archive.', onRefresh: _load),
          const SizedBox(height: 16),
          CustomerSelectorCard(
            title: 'Customer extraction context',
            subtitle: 'Extraction data is read from this customer current FITS archive.',
            onChanged: (_) => _load(),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: _future == null
                ? const Center(child: Text('Select a customer to view extraction data.'))
                : FutureBuilder<Map<String, dynamic>>(
                    key: ValueKey('extraction-$_loadedFor'),
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                      if (snapshot.hasError) return Center(child: Text('Unable to load extraction report: ${snapshot.error}'));
                      final data = snapshot.data ?? <String, dynamic>{};
                      final rows = (data['ocr_text'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
                      final events = (data['extraction_events'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              Chip(label: Text('Text rows: ${rows.length}')),
                              Chip(label: Text('Extraction events: ${events.length}')),
                              Chip(label: Text('Low confidence: ${rows.where((row) => (row['extraction_confidence'] as num? ?? 1) < 0.7).length}')),
                            ],
                          ),
                          const SizedBox(height: 16),
                          Expanded(
                            child: rows.isEmpty
                                ? const Center(child: Text('No extraction text found.'))
                                : ListView.separated(
                                    itemCount: rows.length,
                                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                                    itemBuilder: (context, index) {
                                      final row = rows[index];
                                      final confidence = (row['extraction_confidence'] as num?)?.toDouble();
                                      return Card(
                                        child: Padding(
                                          padding: const EdgeInsets.all(18),
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Row(
                                                children: [
                                                  Expanded(child: Text('${row['filename'] ?? row['object_id'] ?? 'Evidence'}', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
                                                  _ConfidencePill(confidence: confidence),
                                                ],
                                              ),
                                              const SizedBox(height: 8),
                                              Wrap(spacing: 8, runSpacing: 8, children: [
                                                Chip(label: Text('Method: ${row['extraction_method'] ?? '-'}')),
                                                Chip(label: Text('Characters: ${row['character_count'] ?? '-'}')),
                                                Chip(label: Text('Extracted: ${row['extracted_at'] ?? '-'}')),
                                              ]),
                                              const SizedBox(height: 12),
                                              Container(
                                                width: double.infinity,
                                                padding: const EdgeInsets.all(12),
                                                decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
                                                child: SelectableText(_preview('${row['extracted_text'] ?? ''}')),
                                              ),
                                            ],
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                          ),
                        ],
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  String _preview(String text) => text.length <= 800 ? text : '${text.substring(0, 800)}...';
}

class _Header extends StatelessWidget {
  const _Header({required this.title, required this.subtitle, required this.onRefresh});

  final String title;
  final String subtitle;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(subtitle),
          ]),
        ),
        OutlinedButton.icon(onPressed: onRefresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
      ],
    );
  }
}

class _ConfidencePill extends StatelessWidget {
  const _ConfidencePill({required this.confidence});

  final double? confidence;

  @override
  Widget build(BuildContext context) {
    final value = confidence;
    final good = value == null || value >= 0.7;
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: good ? scheme.primaryContainer : scheme.errorContainer),
      child: Text(value == null ? 'Confidence: -' : 'Confidence: ${(value * 100).toStringAsFixed(0)}%', style: TextStyle(color: good ? scheme.onPrimaryContainer : scheme.onErrorContainer)),
    );
  }
}
