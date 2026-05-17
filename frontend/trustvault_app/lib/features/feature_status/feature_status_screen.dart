import 'dart:convert';

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class FeatureStatusScreen extends StatefulWidget {
  const FeatureStatusScreen({super.key, required this.title, required this.description, required this.loader});

  final String title;
  final String description;
  final Future<Map<String, dynamic>> Function(TrustVaultApiClient apiClient) loader;

  @override
  State<FeatureStatusScreen> createState() => _FeatureStatusScreenState();
}

class _FeatureStatusScreenState extends State<FeatureStatusScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.loader(_apiClient);
  }

  void _refresh() {
    setState(() => _future = widget.loader(_apiClient));
  }

  @override
  Widget build(BuildContext context) {
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
                  ],
                ),
              ),
              OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 24),
          Expanded(
            child: FutureBuilder<Map<String, dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(child: Text('Unable to load ${widget.title}: ${snapshot.error}'));
                }
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: SingleChildScrollView(
                      child: SelectableText(_pretty(snapshot.data ?? <String, dynamic>{})),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  String _pretty(Object value) {
    const encoder = JsonEncoder.withIndent('  ');
    return encoder.convert(value);
  }
}
