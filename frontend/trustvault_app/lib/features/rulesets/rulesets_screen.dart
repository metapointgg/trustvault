import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class RulesetsScreen extends StatefulWidget {
  const RulesetsScreen({super.key});

  @override
  State<RulesetsScreen> createState() => _RulesetsScreenState();
}

class _RulesetsScreenState extends State<RulesetsScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getRulesets();
  }

  void _refresh() {
    setState(() {
      _future = _apiClient.getRulesets();
    });
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
                    Text('Rulesets', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text('Evidence completeness rules used to identify missing mandatory evidence across entities and selected customers.'),
                  ],
                ),
              ),
              OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 24),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError) return Center(child: Text('Unable to load rulesets: ${snapshot.error}'));
                final rulesets = (snapshot.data ?? <dynamic>[]).cast<Map<String, dynamic>>();
                if (rulesets.isEmpty) return const Center(child: Text('No rulesets are configured.'));
                return ListView.separated(
                  itemCount: rulesets.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 16),
                  itemBuilder: (context, index) {
                    final ruleset = rulesets[index];
                    final rules = (ruleset['rules'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
                    return Card(
                      child: ExpansionTile(
                        initiallyExpanded: index == 0,
                        leading: const Icon(Icons.fact_check_outlined),
                        title: Text('${ruleset['name']}'),
                        subtitle: Text('Version ${ruleset['version']} • ${ruleset['status']} • ${rules.length} rules'),
                        childrenPadding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                        children: [
                          Align(
                            alignment: Alignment.centerLeft,
                            child: Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: [
                                Chip(label: Text('Required rules: ${rules.where((rule) => rule['required'] == true).length}')),
                                Chip(label: Text('Ruleset ID: ${ruleset['id']}')),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),
                          SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: DataTable(
                              columns: const [
                                DataColumn(label: Text('Required')),
                                DataColumn(label: Text('Rule key')),
                                DataColumn(label: Text('Category')),
                                DataColumn(label: Text('Document type')),
                                DataColumn(label: Text('Max age')),
                                DataColumn(label: Text('Applies when')),
                              ],
                              rows: rules.map((rule) {
                                return DataRow(cells: [
                                  DataCell(Icon(rule['required'] == true ? Icons.check_circle : Icons.remove_circle_outline)),
                                  DataCell(Text('${rule['rule_key'] ?? '-'}')),
                                  DataCell(Text('${rule['category'] ?? '-'}')),
                                  DataCell(Text('${rule['document_type'] ?? '-'}')),
                                  DataCell(Text('${rule['max_age_days'] ?? '-'}')),
                                  DataCell(SizedBox(width: 280, child: Text('${rule['applies_when_json'] ?? {}}', overflow: TextOverflow.ellipsis))),
                                ]);
                              }).toList(),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
