import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/auth_controller.dart';

class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    return Scaffold(
      body: Row(
        children: [
          SizedBox(width: 280, child: _SideNavigation(currentPath: location)),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                const _TopBanner(),
                const Divider(height: 1),
                Expanded(child: child),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TopBanner extends StatelessWidget {
  const _TopBanner();

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: AuthController.instance,
      builder: (context, _) {
        final session = AuthController.instance.session;
        final roles = session?.roles ?? <String>[];
        return Container(
          height: 72,
          padding: const EdgeInsets.symmetric(horizontal: 28),
          color: Theme.of(context).colorScheme.surface,
          child: Row(
            children: [
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('TrustVault Control Centre', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                    Text('Evidence archive, assurance controls and regulator-ready retrieval', style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: roles.take(3).map((role) => Chip(label: Text(role), visualDensity: VisualDensity.compact)).toList(),
              ),
              const SizedBox(width: 16),
              PopupMenuButton<String>(
                tooltip: 'User profile',
                onSelected: (value) {
                  if (value == 'users') context.go('/users');
                  if (value == 'settings') context.go('/settings');
                  if (value == 'sign_out') AuthController.instance.signOut();
                },
                itemBuilder: (context) => [
                  PopupMenuItem<String>(
                    enabled: false,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(session?.displayName ?? 'User', style: const TextStyle(fontWeight: FontWeight.w700)),
                        Text(session?.email ?? '', style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                  ),
                  const PopupMenuDivider(),
                  const PopupMenuItem<String>(value: 'users', child: Text('User admin')),
                  const PopupMenuItem<String>(value: 'settings', child: Text('Settings')),
                  const PopupMenuDivider(),
                  const PopupMenuItem<String>(value: 'sign_out', child: Text('Sign out')),
                ],
                child: Row(
                  children: [
                    CircleAvatar(child: Text(_initials(session?.displayName ?? session?.email ?? 'U'))),
                    const SizedBox(width: 8),
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(session?.displayName ?? 'User', style: const TextStyle(fontWeight: FontWeight.w700)),
                        Text(session?.email ?? '', style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                    const Icon(Icons.arrow_drop_down),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  String _initials(String value) {
    final parts = value.trim().split(RegExp(r'\s+')).where((part) => part.isNotEmpty).toList();
    if (parts.isEmpty) return 'U';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return '${parts.first.substring(0, 1)}${parts.last.substring(0, 1)}'.toUpperCase();
  }
}

class _SideNavigation extends StatelessWidget {
  const _SideNavigation({required this.currentPath});

  final String currentPath;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface,
      child: ListView(
        padding: const EdgeInsets.symmetric(vertical: 20),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
            child: Row(
              children: [
                Icon(Icons.verified_user_outlined, size: 32, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('TrustVault', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                      Text('Evidence assurance', style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
              ],
            ),
          ),
          _NavItem(path: '/', label: 'Dashboard', icon: Icons.dashboard_outlined, currentPath: currentPath),
          _NavGroup(
            title: 'Archive',
            initiallyExpanded: _isInGroup(['/health', '/customers', '/search'], currentPath),
            children: [
              _NavItem(path: '/health', label: 'Health', icon: Icons.health_and_safety_outlined, currentPath: currentPath),
              _NavItem(path: '/customers', label: 'Customers', icon: Icons.business_outlined, currentPath: currentPath),
              _NavItem(path: '/search', label: 'Search & Query', icon: Icons.manage_search_outlined, currentPath: currentPath),
            ],
          ),
          _NavGroup(
            title: 'Assurance',
            initiallyExpanded: _isInGroup(['/completeness', '/extraction', '/retention', '/integrity'], currentPath),
            children: [
              _NavItem(path: '/completeness', label: 'Completeness', icon: Icons.rule_folder_outlined, currentPath: currentPath),
              _NavItem(path: '/extraction', label: 'Extraction', icon: Icons.document_scanner_outlined, currentPath: currentPath),
              _NavItem(path: '/retention', label: 'Legal Hold & Retention', icon: Icons.policy_outlined, currentPath: currentPath),
              _NavItem(path: '/integrity', label: 'Integrity', icon: Icons.verified_outlined, currentPath: currentPath),
            ],
          ),
          _NavGroup(
            title: 'Operations',
            initiallyExpanded: _isInGroup(['/ingestion', '/export'], currentPath),
            children: [
              _NavItem(path: '/ingestion', label: 'Ingestion', icon: Icons.upload_file_outlined, currentPath: currentPath),
              _NavItem(path: '/export', label: 'Export', icon: Icons.file_download_outlined, currentPath: currentPath),
            ],
          ),
          _NavGroup(
            title: 'Administration',
            initiallyExpanded: _isInGroup(['/rulesets', '/audit', '/licence', '/users', '/settings'], currentPath),
            children: [
              _NavItem(path: '/rulesets', label: 'Rulesets', icon: Icons.fact_check_outlined, currentPath: currentPath),
              _NavItem(path: '/users', label: 'User Admin', icon: Icons.manage_accounts_outlined, currentPath: currentPath),
              _NavItem(path: '/settings', label: 'Settings', icon: Icons.settings_outlined, currentPath: currentPath),
              _NavItem(path: '/audit', label: 'Audit Log', icon: Icons.history_edu_outlined, currentPath: currentPath),
              _NavItem(path: '/licence', label: 'Licence', icon: Icons.key_outlined, currentPath: currentPath),
            ],
          ),
        ],
      ),
    );
  }

  bool _isInGroup(List<String> paths, String currentPath) {
    return paths.any((path) => currentPath == path || currentPath.startsWith('$path/'));
  }
}

class _NavGroup extends StatelessWidget {
  const _NavGroup({required this.title, required this.children, required this.initiallyExpanded});

  final String title;
  final List<Widget> children;
  final bool initiallyExpanded;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      initiallyExpanded: initiallyExpanded,
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
      childrenPadding: const EdgeInsets.only(bottom: 8),
      children: children,
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({required this.path, required this.label, required this.icon, required this.currentPath});

  final String path;
  final String label;
  final IconData icon;
  final String currentPath;

  @override
  Widget build(BuildContext context) {
    final selected = currentPath == path || (path != '/' && currentPath.startsWith('$path/'));
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      child: ListTile(
        selected: selected,
        selectedTileColor: Theme.of(context).colorScheme.primaryContainer,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        leading: Icon(icon),
        title: Text(label),
        dense: true,
        onTap: () => context.go(path),
      ),
    );
  }
}
