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
    if (rows.isNotEmpty) {
      final selectedId = _selectedRuleset?['id'];
      _selectedRuleset = rows.cast<Map<String, dynamic>>().where((row) => row['id'] == selectedId).firstOrNull ?? rows.first as Map<String, dynamic>;
    } else {
      _selectedRuleset = null;
    }
    return rows;
  }

  void _refresh() => setState(() => _future = _load());

  Future<void> _saveRuleset({Map<String, dynamic>? ruleset}) async {
    final result = await showDialog<_RulesetEditResult>(context: context, builder: (_) => _RulesetDialog(ruleset: ruleset));
    if (result == null) return;
    try {
      if (ruleset == null) {
        _selectedRuleset = await _apiClient.createRuleset(name: result.name, version: result.version, status: result.status, description: result.description);
      } else {
        _selectedRuleset = await _apiClient.updateRuleset(rulesetId: '${ruleset['id']}', name: result.name, version: result.version, status: result.status, description: result.description);
      }
      _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to save ruleset: $error')));
    }
  }

  Future<void> _deleteRuleset(Map<String, dynamic> ruleset) async {
    final confirm = await showDialog<bool>(context: context, builder: (context) => AlertDialog(title: const Text('Delete ruleset?'), content: Text('Delete ${ruleset['name']} and all of its rules?'), actions: [TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Delete'))]));
    if (confirm != true) return;
    try {
      await _apiClient.deleteRuleset('${ruleset['id']}');
      _selectedRuleset = null;
      _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to delete ruleset: $error')));
    }
  }

  Future<void> _saveRule(Map<String, dynamic> ruleset, {Map<String, dynamic>? rule}) async {
    final result = await showDialog<Map<String, dynamic>>(context: context, builder: (_) => _RuleDialog(rule: rule));
    if (result == null) return;
    try {
      if (rule == null) {
        _selectedRuleset = await _apiClient.createRulesetRule(rulesetId: '${ruleset['id']}', rule: result);
      } else {
        _selectedRuleset = await _apiClient.updateRulesetRule(rulesetId: '${ruleset['id']}', ruleId: '${rule['id']}', rule: result);
      }
      _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to save rule: $error')));
    }
  }

  Future<void> _deleteRule(Map<String, dynamic> ruleset, Map<String, dynamic> rule) async {
    final confirm = await showDialog<bool>(context: context, builder: (context) => AlertDialog(title: const Text('Delete rule?'), content: Text('Delete ${rule['rule_key']}?'), actions: [TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Delete'))]));
    if (confirm != true) return;
    try {
      _selectedRuleset = await _apiClient.deleteRulesetRule(rulesetId: '${ruleset['id']}', ruleId: '${rule['id']}');
      _refresh();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to delete rule: $error')));
    }
  }

  void _showRule(Map<String, dynamic> rule) {
    showDialog<void>(context: context, builder: (context) => AlertDialog(title: Text('${rule['rule_key'] ?? 'Rule detail'}'), content: SizedBox(width: 760, height: 520, child: DecoratedBox(decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)), child: SingleChildScrollView(padding: const EdgeInsets.all(16), child: SelectableText(const JsonEncoder.withIndent('  ').convert(rule), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace'))))), actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))]));
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Rulesets', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)), const SizedBox(height: 8), const Text('View and maintain evidence completeness rules used to identify missing mandatory evidence.')])),
          FilledButton.icon(onPressed: () => _saveRuleset(), icon: const Icon(Icons.add), label: const Text('New ruleset')),
          const SizedBox(width: 12),
          OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
        ]),
        const SizedBox(height: 16),
        Expanded(
          child: FutureBuilder<List<dynamic>>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
              if (snapshot.hasError) return Center(child: Text('Unable to load rulesets: ${snapshot.error}'));
              final rulesets = (snapshot.data ?? <dynamic>[]).cast<Map<String, dynamic>>();
              if (rulesets.isEmpty) return const Center(child: Text('No rulesets are configured. Create a ruleset to begin.'));
              final selected = _selectedRuleset ?? rulesets.first;
              final rules = (selected['rules'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
              return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SizedBox(width: 460, child: Card(child: SingleChildScrollView(child: DataTable(showCheckboxColumn: false, columns: const [DataColumn(label: Text('Ruleset')), DataColumn(label: Text('Status')), DataColumn(label: Text('Rules'))], rows: rulesets.map((ruleset) => DataRow(selected: ruleset['id'] == selected['id'], onSelectChanged: (_) => setState(() => _selectedRuleset = ruleset), cells: [DataCell(SizedBox(width: 210, child: Text('${ruleset['name'] ?? '-'}', overflow: TextOverflow.ellipsis))), DataCell(Text('${ruleset['status'] ?? '-'}')), DataCell(Text('${ruleset['rule_count'] ?? '-'}'))])).toList())))),
                const SizedBox(width: 16),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [Chip(label: Text('Name: ${selected['name']}')), Chip(label: Text('Version: ${selected['version']}')), Chip(label: Text('Status: ${selected['status']}')), Chip(label: Text('Required: ${rules.where((rule) => rule['required'] == true).length}')), OutlinedButton.icon(onPressed: () => _saveRuleset(ruleset: selected), icon: const Icon(Icons.edit_outlined), label: const Text('Edit ruleset')), OutlinedButton.icon(onPressed: () => _deleteRuleset(selected), icon: const Icon(Icons.delete_outline), label: const Text('Delete')), FilledButton.icon(onPressed: () => _saveRule(selected), icon: const Icon(Icons.add), label: const Text('Add rule'))]),
                  const SizedBox(height: 12),
                  Expanded(child: Card(child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: SingleChildScrollView(child: DataTable(columns: const [DataColumn(label: Text('Required')), DataColumn(label: Text('Rule key')), DataColumn(label: Text('Category')), DataColumn(label: Text('Document type')), DataColumn(label: Text('Max age')), DataColumn(label: Text('Applies when')), DataColumn(label: Text('Actions'))], rows: rules.map((rule) => DataRow(cells: [DataCell(Icon(rule['required'] == true ? Icons.check_circle : Icons.remove_circle_outline)), DataCell(Text('${rule['rule_key'] ?? '-'}')), DataCell(Text('${rule['category'] ?? '-'}')), DataCell(Text('${rule['document_type'] ?? '-'}')), DataCell(Text('${rule['max_age_days'] ?? '-'}')), DataCell(SizedBox(width: 280, child: Text('${rule['applies_when_json'] ?? {}}', overflow: TextOverflow.ellipsis))), DataCell(Row(mainAxisSize: MainAxisSize.min, children: [TextButton(onPressed: () => _showRule(rule), child: const Text('View')), TextButton(onPressed: () => _saveRule(selected, rule: rule), child: const Text('Edit')), TextButton(onPressed: () => _deleteRule(selected, rule), child: const Text('Delete'))]))])).toList()))))),
                ])),
              ]);
            },
          ),
        ),
      ]),
    );
  }
}

class _RulesetEditResult {
  const _RulesetEditResult({required this.name, required this.version, required this.status, this.description});
  final String name;
  final int version;
  final String status;
  final String? description;
}

class _RulesetDialog extends StatefulWidget {
  const _RulesetDialog({this.ruleset});
  final Map<String, dynamic>? ruleset;
  @override
  State<_RulesetDialog> createState() => _RulesetDialogState();
}

class _RulesetDialogState extends State<_RulesetDialog> {
  late final TextEditingController _name = TextEditingController(text: '${widget.ruleset?['name'] ?? ''}');
  late final TextEditingController _version = TextEditingController(text: '${widget.ruleset?['version'] ?? 1}');
  late final TextEditingController _description = TextEditingController(text: '${widget.ruleset?['description'] ?? ''}');
  late String _status = '${widget.ruleset?['status'] ?? 'draft'}';
  @override
  void dispose() { _name.dispose(); _version.dispose(); _description.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => AlertDialog(title: Text(widget.ruleset == null ? 'New ruleset' : 'Edit ruleset'), content: SizedBox(width: 520, child: Column(mainAxisSize: MainAxisSize.min, children: [TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name', border: OutlineInputBorder())), const SizedBox(height: 12), TextField(controller: _version, decoration: const InputDecoration(labelText: 'Version', border: OutlineInputBorder())), const SizedBox(height: 12), DropdownButtonFormField<String>(value: _status, decoration: const InputDecoration(labelText: 'Status', border: OutlineInputBorder()), items: const ['draft', 'active', 'inactive', 'archived'].map((value) => DropdownMenuItem(value: value, child: Text(value))).toList(), onChanged: (value) => setState(() => _status = value ?? 'draft')), const SizedBox(height: 12), TextField(controller: _description, minLines: 2, maxLines: 4, decoration: const InputDecoration(labelText: 'Description', border: OutlineInputBorder()))])), actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.of(context).pop(_RulesetEditResult(name: _name.text.trim(), version: int.tryParse(_version.text.trim()) ?? 1, status: _status, description: _description.text.trim().isEmpty ? null : _description.text.trim())), child: const Text('Save'))]);
}

class _RuleDialog extends StatefulWidget {
  const _RuleDialog({this.rule});
  final Map<String, dynamic>? rule;
  @override
  State<_RuleDialog> createState() => _RuleDialogState();
}

class _RuleDialogState extends State<_RuleDialog> {
  late final TextEditingController _ruleKey = TextEditingController(text: '${widget.rule?['rule_key'] ?? ''}');
  late final TextEditingController _category = TextEditingController(text: '${widget.rule?['category'] ?? ''}');
  late final TextEditingController _documentType = TextEditingController(text: '${widget.rule?['document_type'] ?? ''}');
  late final TextEditingController _maxAge = TextEditingController(text: '${widget.rule?['max_age_days'] ?? ''}');
  late final TextEditingController _appliesWhen = TextEditingController(text: const JsonEncoder.withIndent('  ').convert(widget.rule?['applies_when_json'] ?? <String, dynamic>{}));
  late bool _required = widget.rule?['required'] != false;
  @override
  void dispose() { _ruleKey.dispose(); _category.dispose(); _documentType.dispose(); _maxAge.dispose(); _appliesWhen.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => AlertDialog(title: Text(widget.rule == null ? 'New rule' : 'Edit rule'), content: SizedBox(width: 620, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [TextField(controller: _ruleKey, decoration: const InputDecoration(labelText: 'Rule key', border: OutlineInputBorder())), const SizedBox(height: 12), TextField(controller: _category, decoration: const InputDecoration(labelText: 'Category', border: OutlineInputBorder())), const SizedBox(height: 12), TextField(controller: _documentType, decoration: const InputDecoration(labelText: 'Document type', border: OutlineInputBorder())), const SizedBox(height: 12), TextField(controller: _maxAge, decoration: const InputDecoration(labelText: 'Max age days', border: OutlineInputBorder())), SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Required'), value: _required, onChanged: (value) => setState(() => _required = value)), TextField(controller: _appliesWhen, minLines: 4, maxLines: 8, decoration: const InputDecoration(labelText: 'Applies when JSON', border: OutlineInputBorder()))]))), actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')), FilledButton(onPressed: () { Map<String, dynamic> appliesWhen; try { appliesWhen = jsonDecode(_appliesWhen.text) as Map<String, dynamic>; } catch (_) { appliesWhen = <String, dynamic>{}; } Navigator.of(context).pop(<String, dynamic>{'rule_key': _ruleKey.text.trim(), 'category': _category.text.trim(), 'document_type': _documentType.text.trim(), 'required': _required, 'applies_when_json': appliesWhen, if (_maxAge.text.trim().isNotEmpty) 'max_age_days': int.tryParse(_maxAge.text.trim())}); }, child: const Text('Save'))]);
}
