import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

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
          Expanded(child: child),
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

class _Destination {
  const _Destination(this.path, this.label, this.icon, this.selectedIcon);

  final String path;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}
