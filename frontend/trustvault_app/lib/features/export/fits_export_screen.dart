import 'dart:html' as html;

import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';

class FitsExportScreen extends StatefulWidget {
  const FitsExportScreen({super.key});

  @override
  State<FitsExportScreen> createState() => _FitsExportScreenState();
}

class _FitsExportScreenState extends State<FitsExportScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  final TextEditingController _filterController = TextEditingController();
  late Future<List<dynamic>> _customersFuture;
  String _filter = '';
  bool _downloading = false;

  @override
  void initState() {
    super.initState();
    _customersFuture = _apiClient.getCustomers();
    _filterController.addListener(() =>
        setState(() => _filter = _filterController.text.trim().toLowerCase()));
  }

  @override
  void dispose() {
    _filterController.dispose();
    super.dispose();
  }

  Future<void> _downloadCurrentFits(Map<String, dynamic> customer) async {
    final containerVersionId = customer['current_container_version_id'];
    if (containerVersionId == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Customer has no current FITS archive.')));
      return;
    }
    setState(() => _downloading = true);
    try {
      final bytes = await _apiClient.downloadFitsBytes('$containerVersionId');
      final blob = html.Blob(<dynamic>[bytes], 'application/fits');
      final url = html.Url.createObjectUrlFromBlob(blob);
      final filename =
          '${customer['external_id'] ?? 'trustvault'}-${customer['current_container_version_number'] ?? 'current'}.fits';
      html.AnchorElement(href: url)
        ..download = filename
        ..style.display = 'none'
        ..click();
      html.Url.revokeObjectUrl(url);
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Downloaded $filename')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Download failed: $error')));
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  List<Map<String, dynamic>> _filtered(List<dynamic> customers) {
    final rows = customers.cast<Map<String, dynamic>>();
    if (_filter.isEmpty) return rows;
    return rows.where((customer) {
      final haystack =
          '${customer['external_id']} ${customer['display_name']} ${customer['risk_rating']} ${customer['jurisdiction']}'
              .toLowerCase();
      return haystack.contains(_filter);
    }).toList();
  }

  Future<void> _showFitsContents(Map<String, dynamic> customer) async {
    final versions = await _apiClient
        .getEntityContainerVersions('${customer['external_id']}');
    if (!mounted) return;
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${customer['display_name']} FITS contents'),
        content: SizedBox(
          width: 980,
          height: 620,
          child: versions.isEmpty
              ? const Text('No FITS versions available.')
              : SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: SingleChildScrollView(
                    child: DataTable(
                      columns: const [
                        DataColumn(label: Text('Version')),
                        DataColumn(label: Text('Status')),
                        DataColumn(label: Text('Evidence objects')),
                        DataColumn(label: Text('Size bytes')),
                        DataColumn(label: Text('SHA-256')),
                        DataColumn(label: Text('Storage URI')),
                      ],
                      rows:
                          versions.cast<Map<String, dynamic>>().map((version) {
                        return DataRow(cells: [
                          DataCell(Text('${version['version_number'] ?? '-'}')),
                          DataCell(Text('${version['status'] ?? '-'}')),
                          DataCell(Text(
                              '${version['evidence_object_count'] ?? '-'}')),
                          DataCell(Text('${version['size_bytes'] ?? '-'}')),
                          DataCell(SizedBox(
                              width: 300,
                              child: SelectableText(
                                  '${version['sha256'] ?? '-'}'))),
                          DataCell(SizedBox(
                              width: 420,
                              child: SelectableText(
                                  '${version['storage_uri'] ?? '-'}'))),
                        ]);
                      }).toList(),
                    ),
                  ),
                ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'))
        ],
      ),
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
                    Text('Export',
                        style: Theme.of(context)
                            .textTheme
                            .displaySmall
                            ?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    const Text(
                        'Search for a customer, review the current FITS archive and download the authenticated source-of-truth FITS file.'),
                  ],
                ),
              ),
              OutlinedButton.icon(
                  onPressed: () => setState(
                      () => _customersFuture = _apiClient.getCustomers()),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _filterController,
            decoration: const InputDecoration(
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.search),
                labelText:
                    'Search customers by name, ID, risk or jurisdiction'),
          ),
          const SizedBox(height: 16),
          if (_downloading) const LinearProgressIndicator(),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _customersFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done)
                  return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError)
                  return Center(
                      child:
                          Text('Unable to load customers: ${snapshot.error}'));
                final customers = _filtered(snapshot.data ?? <dynamic>[]);
                if (customers.isEmpty)
                  return const Center(
                      child: Text('No customers available for export.'));
                return Card(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: SingleChildScrollView(
                      child: DataTable(
                        columns: const [
                          DataColumn(label: Text('Customer ID')),
                          DataColumn(label: Text('Name')),
                          DataColumn(label: Text('Risk')),
                          DataColumn(label: Text('Jurisdiction')),
                          DataColumn(label: Text('Version')),
                          DataColumn(label: Text('Storage URI')),
                          DataColumn(label: Text('Actions')),
                        ],
                        rows: customers.map((customer) {
                          final hasFits =
                              customer['has_current_fits_container'] == true;
                          return DataRow(cells: [
                            DataCell(Text('${customer['external_id'] ?? '-'}')),
                            DataCell(SizedBox(
                                width: 220,
                                child: Text(
                                    '${customer['display_name'] ?? '-'}',
                                    overflow: TextOverflow.ellipsis))),
                            DataCell(Text('${customer['risk_rating'] ?? '-'}')),
                            DataCell(
                                Text('${customer['jurisdiction'] ?? '-'}')),
                            DataCell(Text(
                                '${customer['current_container_version_number'] ?? '-'}')),
                            DataCell(SizedBox(
                                width: 460,
                                child: SelectableText(
                                    '${customer['current_container_storage_uri'] ?? '-'}'))),
                            DataCell(Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                TextButton.icon(
                                    onPressed: () =>
                                        _showFitsContents(customer),
                                    icon: const Icon(Icons.list_alt_outlined),
                                    label: const Text('Contents')),
                                const SizedBox(width: 8),
                                FilledButton.icon(
                                    onPressed: hasFits && !_downloading
                                        ? () => _downloadCurrentFits(customer)
                                        : null,
                                    icon: const Icon(Icons.download),
                                    label: const Text('Download FITS')),
                              ],
                            )),
                          ]);
                        }).toList(),
                      ),
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
}
