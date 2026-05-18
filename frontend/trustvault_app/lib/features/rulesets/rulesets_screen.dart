import 'dart:convert';

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
  Map<String, dynamic>? _selectedRuleset;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<dynamic>> _load() async {
    final rows = await _apiClient.getRulesets();
    if (rows.isNotEmpty && _selectedRuleset == null) {
      _selectedRuleset = rows.first as Map<String, dynamic>;
    }
    return rows;
  }

  void _refresh() {
    setState(() {
      _future = _load();
    });
  }

  void _showRule(Map<String, dynamic> rule) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${rule['rule_key'] ?? 'Rule detail'}'),
        content: SizedBox(
          width: 760,
          height: 520,
          child: DecoratedBox(
            decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: SelectableText(const JsonEncoder.withIndent('  ').convert(rule), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
            ),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  void _showEditUnavailable() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Ruleset amendment is not yet available: backend create/update rule endpoints are required.')),
    );
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
                    const Text('View evidence completeness rules used to identify missing mandatory evidence. Editing requires the rule-management API endpoints to be added.'),
                  ],
                ),
              ),
              OutlinedButton.icon(onPressed: _showEditUnavailable, icon: const Icon(Icons.edit_outlined), label: const Text('Amend ruleset')),
              const SizedBox(width: 12),
              OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 16),
          _Notice(),
          const SizedBox(height: 16),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError) return Center(child: Text('Unable to load rulesets: ${snapshot.error}'));
                final rulesets = (snapshot.data ?? <dynamic>[]).cast<Map<String, dynamic>>();
                if (rulesets.isEmpty) return const Center(child: Text('No rulesets are configured.'));
                final selected = _selectedRuleset ?? rulesets.first;
                final rules = (selected['rules'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 420,
                      child: Card(
                        child: SingleChildScrollView(
                          child: DataTable(
                            columns: const [
                              DataColumn(label: Text('Ruleset')),
                              DataColumn(label: Text('Status')),
                              DataColumn(label: Text('Rules')),
                            ],
                            rows: rulesets.map((ruleset) {
                              final isSelected = ruleset['id'] == selected['id'];
                              return DataRow(
                                selected: isSelected,
                                onSelectChanged: (_) => setState(() => _selectedRuleset = ruleset),
                                cells: [
                                  DataCell(SizedBox(width: 180, child: Text('${ruleset['name'] ?? '-'}', overflow: TextOverflow.ellipsis))),
                                  DataCell(Text('${ruleset['status'] ?? '-'}')),
                                  DataCell(Text('${ruleset['rule_count'] ?? '-'}')),
                                ],
                              );
                            }).toList(),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(spacing: 8, runSpacing: 8, children: [
                            Chip(label: Text('Name: ${selected['name']}')),
                            Chip(label: Text('Version: ${selected['version']}')),
                            Chip(label: Text('Status: ${selected['status']}')),
                            Chip(label: Text('Required: ${rules.where((rule) => rule['required'] == true).length}')),
                            Chip(label: Text('Ruleset ID: ${selected['id']}')),
                          ]),
                          const SizedBox(height: 12),
                          Expanded(
                            child: Card(
                              child: SingleChildScrollView(
                                scrollDirection: Axis.horizontal,
                                child: SingleChildScrollView(
                                  child: DataTable(
                                    columns: const [
                                      DataColumn(label: Text('Required')),
                                      DataColumn(label: Text('Rule key')),
                                      DataColumn(label: Text('Category')),
                                      DataColumn(label: Text('Document type')),
                                      DataColumn(label: Text('Max age')),
                                      DataColumn(label: Text('Applies when')),
                                      DataColumn(label: Text('Actions')),
                                    ],
                                    rows: rules.map((rule) {
                                      return DataRow(cells: [
                                        DataCell(Icon(rule['required'] == true ? Icons.check_circle : Icons.remove_circle_outline)),
                                        DataCell(Text('${rule['rule_key'] ?? '-'}')),
                                        DataCell(Text('${rule['category'] ?? '-'}')),
                                        DataCell(Text('${rule['document_type'] ?? '-'}')),
                                        DataCell(Text('${rule['max_age_days'] ?? '-'}')),
                                        DataCell(SizedBox(width: 280, child: Text('${rule['applies_when_json'] ?? {}}', overflow: TextOverflow.ellipsis))),
                                        DataCell(Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            TextButton.icon(onPressed: () => _showRule(rule), icon: const Icon(Icons.visibility_outlined), label: const Text('View')),
                                            TextButton.icon(onPressed: _showEditUnavailable, icon: const Icon(Icons.edit_outlined), label: const Text('Edit')),
                                          ],
                                        )),
                                      ]);
                                    }).toList(),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
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
}

class _Notice extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: Theme.of(context).colorScheme.secondaryContainer, borderRadius: BorderRadius.circular(12)),
      child: Text(
        'Current API supports listing rulesets and ensuring the default ruleset. Create/update/delete rule endpoints are still required before production users can amend rules safely.',
        style: TextStyle(color: Theme.of(context).colorScheme.onSecondaryContainer),
      ),
    );
  }
}
