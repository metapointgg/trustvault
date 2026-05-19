import 'dart:convert';

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../shared/trustvault_data_grid.dart';

class JobsScreen extends StatefulWidget {
  const JobsScreen({super.key});

  @override
  State<JobsScreen> createState() => _JobsScreenState();
}

class _JobsScreenState extends State<JobsScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _future;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getJobs();
  }

  Future<void> _submitJob(String jobType) async {
    setState(() => _submitting = true);
    try {
      await _apiClient.createJob(jobType);
      final nextFuture = _apiClient.getJobs();
      if (!mounted) return;
      setState(() {
        _future = nextFuture;
        _submitting = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _submitting = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to submit job: $error')));
    }
  }

  void _refresh() => setState(() => _future = _apiClient.getJobs());

  Map<String, dynamic> _row(Map<String, dynamic> job) => <String, dynamic>{
        ...job,
        'payload_text': jsonEncode(job['payload'] ?? job['payload_json'] ?? <String, dynamic>{}),
        'result_text': jsonEncode(job['result'] ?? job['result_json'] ?? <String, dynamic>{}),
      };

  void _showJob(Map<String, dynamic> job) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${job['job_type'] ?? 'Job'}'),
        content: SizedBox(
          width: 920,
          height: 620,
          child: DecoratedBox(
            decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: SelectableText(const JsonEncoder.withIndent('  ').convert(job), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
            ),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close'))],
      ),
    );
  }

  List<TrustVaultDataGridColumn> _columns() => [
        const TrustVaultDataGridColumn(key: 'created_at', label: 'Created', width: 210),
        const TrustVaultDataGridColumn(key: 'job_type', label: 'Job type', width: 220),
        const TrustVaultDataGridColumn(key: 'status', label: 'Status', width: 120),
        const TrustVaultDataGridColumn(key: 'id', label: 'Job ID', width: 300, visibleByDefault: false),
        const TrustVaultDataGridColumn(key: 'correlation_id', label: 'Correlation', width: 300),
        const TrustVaultDataGridColumn(key: 'created_by_user_id', label: 'Created by', width: 220, visibleByDefault: false),
        const TrustVaultDataGridColumn(key: 'started_at', label: 'Started', width: 210, visibleByDefault: false),
        const TrustVaultDataGridColumn(key: 'completed_at', label: 'Completed', width: 210),
        const TrustVaultDataGridColumn(key: 'error_message', label: 'Error', width: 360),
        const TrustVaultDataGridColumn(key: 'payload_text', label: 'Payload', width: 420, visibleByDefault: false),
        const TrustVaultDataGridColumn(key: 'result_text', label: 'Result', width: 420, visibleByDefault: false),
        TrustVaultDataGridColumn(key: 'actions', label: 'Actions', width: 80, sortable: false, valueBuilder: (_) => '', cellBuilder: (row) => TextButton.icon(onPressed: () => _showJob(row), icon: const Icon(Icons.visibility_outlined), label: const Text('View'))),
      ];

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      thumbVisibility: true,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Jobs / ingestion history', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)), const SizedBox(height: 8), const Text('Submit and monitor TrustVault background jobs and ingestion activity.')])),
            OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            const SizedBox(width: 12),
            FilledButton.icon(onPressed: _submitting ? null : () => _submitJob('rebuild_index'), icon: _submitting ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.add), label: Text(_submitting ? 'Submitting...' : 'Submit test job')),
          ]),
          const SizedBox(height: 24),
          FutureBuilder<List<dynamic>>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) return const SizedBox(height: 520, child: Center(child: CircularProgressIndicator()));
              if (snapshot.hasError) return SizedBox(height: 520, child: Center(child: Text('Unable to load jobs: ${snapshot.error}')));
              final rows = (snapshot.data ?? <dynamic>[]).cast<Map<String, dynamic>>().map(_row).toList();
              return TrustVaultDataGrid(title: 'Jobs / ingestion history', subtitle: 'Search, sort, show/hide columns and export background job history.', rows: rows, columns: _columns(), initialSortColumnKey: 'created_at', initialSortAscending: false, onRowTap: _showJob, exportFilename: 'trustvault-jobs.csv', emptyText: 'No jobs have been submitted yet.', height: 680, dense: true);
            },
          ),
          const SizedBox(height: 32),
        ]),
      ),
    );
  }
}
