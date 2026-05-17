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

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getJobs();
  }

  Future<void> _submitJob(String jobType) async {
    await _apiClient.createJob(jobType);
    setState(() => _future = _apiClient.getJobs());
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
              FilledButton.icon(
                onPressed: () => _submitJob('rebuild_index'),
                icon: const Icon(Icons.add),
                label: const Text('Submit test job'),
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
                        subtitle: Text('ID: ${job['id']}\nCorrelation: ${job['correlation_id']}'),
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
