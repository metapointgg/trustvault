import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/api/trustvault_api_client.dart';
import 'selected_customer.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _customersFuture;

  static const List<_Destination> _destinations = [
    _Destination('/', 'Dashboard', Icons.dashboard_outlined, Icons.dashboard),
    _Destination('/health', 'Health', Icons.health_and_safety_outlined, Icons.health_and_safety),
    _Destination('/comparison', 'Comparison', Icons.compare_arrows_outlined, Icons.compare_arrows),
    _Destination('/customers', 'Customers', Icons.business_outlined, Icons.business),
    _Destination('/search', 'Search', Icons.manage_search_outlined, Icons.manage_search),
    _Destination('/completeness', 'Completeness', Icons.rule_folder_outlined, Icons.rule_folder),
    _Destination('/rulesets', 'Rulesets', Icons.fact_check_outlined, Icons.fact_check),
    _Destination('/ingestion', 'Ingestion', Icons.upload_file_outlined, Icons.upload_file),
    _Destination('/extraction', 'Extraction', Icons.document_scanner_outlined, Icons.document_scanner),
    _Destination('/retention', 'Retention', Icons.policy_outlined, Icons.policy),
    _Destination('/integrity', 'Integrity', Icons.verified_outlined, Icons.verified),
    _Destination('/export', 'Export', Icons.file_download_outlined, Icons.file_download),
    _Destination('/api', 'API', Icons.api_outlined, Icons.api),
    _Destination('/fits', 'FITS', Icons.data_object_outlined, Icons.data_object),
    _Destination('/jobs', 'Jobs', Icons.work_history_outlined, Icons.work_history),
    _Destination('/audit', 'Audit', Icons.history_edu_outlined, Icons.history_edu),
    _Destination('/licence', 'Licence', Icons.key_outlined, Icons.key),
  ];

  @override
  void initState() {
    super.initState();
    _customersFuture = _apiClient.getCustomers();
    SelectedCustomerController.refreshToken.addListener(_refreshCustomers);
  }

  @override
  void dispose() {
    SelectedCustomerController.refreshToken.removeListener(_refreshCustomers);
    super.dispose();
  }

  void _refreshCustomers() {
    setState(() {
      _customersFuture = _apiClient.getCustomers();
    });
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;

    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            extended: MediaQuery.of(context).size.width > 1160,
            selectedIndex: _selectedIndex(location),
            onDestinationSelected: (index) => context.go(_destinations[index].path),
            leading: const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Icon(Icons.verified_user_outlined, size: 32),
            ),
            destinations: _destinations
                .map(
                  (item) => NavigationRailDestination(
                    icon: Icon(item.icon),
                    selectedIcon: Icon(item.selectedIcon),
                    label: Text(item.label),
                  ),
                )
                .toList(),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                _CustomerContextBar(customersFuture: _customersFuture, onRefresh: _refreshCustomers),
                const Divider(height: 1),
                Expanded(child: widget.child),
              ],
            ),
          ),
        ],
      ),
    );
  }

  int _selectedIndex(String location) {
    for (var i = 0; i < _destinations.length; i++) {
      final path = _destinations[i].path;
      if (path == '/' && location == '/') return i;
      if (path != '/' && location.startsWith(path)) return i;
    }
    return 0;
  }
}

class _CustomerContextBar extends StatelessWidget {
  const _CustomerContextBar({required this.customersFuture, required this.onRefresh});

  final Future<List<dynamic>> customersFuture;
  final VoidCallback onRefresh;

  Map<String, dynamic>? _findCustomer(List<dynamic> customers, String? externalId) {
    for (final item in customers) {
      final customer = item as Map<String, dynamic>;
      if (customer['external_id']?.toString() == externalId) {
        return customer;
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          const Icon(Icons.business_outlined),
          const SizedBox(width: 12),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: customersFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Text('Loading customers...');
                }
                if (snapshot.hasError) {
                  return Text('Unable to load customers: ${snapshot.error}');
                }
                final customers = (snapshot.data ?? <dynamic>[]).cast<dynamic>();
                if (customers.isEmpty) {
                  SelectedCustomerController.select(null);
                  return const Text('No customer selected. Upload a source folder to begin.');
                }
                final current = SelectedCustomerController.selected.value;
                if (current == null || _findCustomer(customers, current['external_id']?.toString()) == null) {
                  SelectedCustomerController.select(customers.first as Map<String, dynamic>);
                }
                return ValueListenableBuilder<Map<String, dynamic>?>(
                  valueListenable: SelectedCustomerController.selected,
                  builder: (context, selected, _) {
                    final selectedExternalId = selected?['external_id']?.toString();
                    final selectedValue = _findCustomer(customers, selectedExternalId)?['external_id']?.toString() ??
                        (customers.first as Map<String, dynamic>)['external_id']?.toString();
                    return DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        isExpanded: true,
                        value: selectedValue,
                        items: customers.map((item) {
                          final customer = item as Map<String, dynamic>;
                          final label = '${customer['display_name'] ?? customer['external_id']} (${customer['external_id']})';
                          return DropdownMenuItem<String>(
                            value: customer['external_id']?.toString(),
                            child: Text(label, overflow: TextOverflow.ellipsis),
                          );
                        }).toList(),
                        onChanged: (value) {
                          SelectedCustomerController.select(_findCustomer(customers, value));
                        },
                      ),
                    );
                  },
                );
              },
            ),
          ),
          const SizedBox(width: 12),
          IconButton(onPressed: onRefresh, icon: const Icon(Icons.refresh), tooltip: 'Refresh customers'),
        ],
      ),
    );
  }
}

class _Destination {
  const _Destination(this.path, this.label, this.icon, this.selectedIcon);

  final String path;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}
