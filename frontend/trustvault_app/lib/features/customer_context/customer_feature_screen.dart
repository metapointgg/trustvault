import 'dart:convert';

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/selected_customer.dart';

class CustomerFeatureScreen extends StatefulWidget {
  const CustomerFeatureScreen({
    super.key,
    required this.title,
    required this.description,
    required this.loader,
    this.actionLabel,
  });

  final String title;
  final String description;
  final Future<Map<String, dynamic>> Function(TrustVaultApiClient apiClient, String entityExternalId) loader;
  final String? actionLabel;

  @override
  State<CustomerFeatureScreen> createState() => _CustomerFeatureScreenState();
}

class _CustomerFeatureScreenState extends State<CustomerFeatureScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  Future<Map<String, dynamic>>? _future;
  String? _loadedFor;

  @override
  void initState() {
    super.initState();
    SelectedCustomerController.selected.addListener(_loadForSelectedCustomer);
    _loadForSelectedCustomer();
  }

  @override
  void dispose() {
    SelectedCustomerController.selected.removeListener(_loadForSelectedCustomer);
    super.dispose();
  }

  void _loadForSelectedCustomer() {
    final externalId = SelectedCustomerController.externalId;
    if (externalId == null || externalId.isEmpty) {
      setState(() {
        _loadedFor = null;
        _future = null;
      });
      return;
    }
    final nextFuture = widget.loader(_apiClient, externalId);
    setState(() {
      _loadedFor = externalId;
      _future = nextFuture;
    });
  }

  @override
  Widget build(BuildContext context) {
    final selectedLabel = SelectedCustomerController.displayLabel;
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(widget.title, style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    Text(widget.description),
                    const SizedBox(height: 8),
                    Text('Customer: $selectedLabel', style: Theme.of(context).textTheme.titleSmall),
                  ],
                ),
              ),
              OutlinedButton.icon(onPressed: _loadForSelectedCustomer, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 24),
          Expanded(
            child: _future == null
                ? const Center(child: Text('Select a customer to continue.'))
                : FutureBuilder<Map<String, dynamic>>(
                    key: ValueKey('${widget.title}-$_loadedFor'),
                    future: _future,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (snapshot.hasError) {
                        return Center(child: Text('Unable to load ${widget.title}: ${snapshot.error}'));
                      }
                      final data = snapshot.data ?? <String, dynamic>{};
                      return _StructuredJsonCard(title: widget.title, data: data);
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _StructuredJsonCard extends StatelessWidget {
  const _StructuredJsonCard({required this.title, required this.data});

  final String title;
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final pretty = const JsonEncoder.withIndent('  ').convert(data);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SummaryStrip(data: data),
            const SizedBox(height: 16),
            Expanded(
              child: SingleChildScrollView(
                child: SelectableText(pretty),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryStrip extends StatelessWidget {
  const _SummaryStrip({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final values = <String, String>{};
    for (final key in ['score', 'missing_count', 'present_count', 'required_count', 'checked_count', 'entity_count', 'result_count']) {
      if (data.containsKey(key)) values[key] = '${data[key]}';
    }
    if (data.containsKey('checks')) {
      final checks = data['checks'] as List<dynamic>? ?? <dynamic>[];
      values['checks'] = '${checks.length}';
      values['failures'] = '${checks.where((item) => (item as Map<String, dynamic>)['status'] == 'fail').length}';
    }
    if (values.isEmpty) return const SizedBox.shrink();
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: values.entries.map((entry) {
        return Chip(label: Text('${entry.key}: ${entry.value}'));
      }).toList(),
    );
  }
}
