import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

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
    setState(() {
      _submitting = true;
    });
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
      setState(() {
        _submitting = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to submit job: $error')));
    }
  }

  void _refresh() {
    final nextFuture = _apiClient.getJobs();
    setState(() {
      _future = nextFuture;
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
                    Text('Jobs', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text('Submit and monitor TrustVault background jobs.'),
                  ],
                ),
              ),
              OutlinedButton.icon(
                onPressed: _refresh,
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh'),
              ),
              const SizedBox(width: 12),
              FilledButton.icon(
                onPressed: _submitting ? null : () => _submitJob('rebuild_index'),
                icon: _submitting
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.add),
                label: Text(_submitting ? 'Submitting...' : 'Submit test job'),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(child: Text('Unable to load jobs: ${snapshot.error}'));
                }
                final jobs = snapshot.data ?? <dynamic>[];
                if (jobs.isEmpty) {
                  return const Center(child: Text('No jobs have been submitted yet.'));
                }
                return ListView.separated(
                  itemCount: jobs.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final job = jobs[index] as Map<String, dynamic>;
                    return Card(
                      child: ListTile(
                        leading: const Icon(Icons.work_history_outlined),
                        title: Text('${job['job_type']}'),
                        subtitle: Text(
                          'ID: ${job['id']}\n'
                          'Correlation: ${job['correlation_id']}\n'
                          'Created: ${job['created_at']}\n'
                          'Completed: ${job['completed_at'] ?? '-'}',
                        ),
                        trailing: Chip(label: Text('${job['status']}')),
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
