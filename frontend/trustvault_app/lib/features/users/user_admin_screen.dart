import 'package:flutter/material.dart';

import '../../core/api/trustvault_api_client.dart';
import '../../core/auth/auth_controller.dart';

class UserAdminScreen extends StatefulWidget {
  const UserAdminScreen({super.key});

  @override
  State<UserAdminScreen> createState() => _UserAdminScreenState();
}

class _UserAdminScreenState extends State<UserAdminScreen> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<Map<String, dynamic>> _usersFuture;
  late Future<Map<String, dynamic>> _rolesFuture;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _usersFuture = _apiClient.getUsers();
    _rolesFuture = _apiClient.getAvailableRoles();
  }

  Future<void> _refresh() async {
    setState(_reload);
  }

  Future<void> _showCreateDialog(List<String> roles) async {
    final emailController = TextEditingController();
    final displayNameController = TextEditingController();
    final selectedRoles = <String>{roles.contains('Read-only Auditor') ? 'Read-only Auditor' : roles.first};
    String status = 'active';

    await showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Create local user'),
              content: SizedBox(
                width: 520,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(controller: emailController, decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder())),
                    const SizedBox(height: 12),
                    TextField(controller: displayNameController, decoration: const InputDecoration(labelText: 'Display name', border: OutlineInputBorder())),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: status,
                      decoration: const InputDecoration(labelText: 'Status', border: OutlineInputBorder()),
                      items: const [
                        DropdownMenuItem(value: 'active', child: Text('Active')),
                        DropdownMenuItem(value: 'disabled', child: Text('Disabled')),
                      ],
                      onChanged: (value) => setDialogState(() => status = value ?? 'active'),
                    ),
                    const SizedBox(height: 12),
                    Align(alignment: Alignment.centerLeft, child: Text('Roles', style: Theme.of(context).textTheme.titleSmall)),
                    Wrap(
                      spacing: 8,
                      children: roles.map((role) {
                        return FilterChip(
                          label: Text(role),
                          selected: selectedRoles.contains(role),
                          onSelected: (selected) {
                            setDialogState(() {
                              if (selected) {
                                selectedRoles.add(role);
                              } else {
                                selectedRoles.remove(role);
                              }
                            });
                          },
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 12),
                    const Text('The user is created in the local database. Activation/credential reset should be handled through the controlled operational process for this deployment.'),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
                FilledButton(
                  onPressed: () async {
                    await _apiClient.createUser(
                      email: emailController.text.trim(),
                      displayName: displayNameController.text.trim(),
                      roles: selectedRoles.toList(),
                      status: status,
                    );
                    if (mounted) {
                      Navigator.of(context).pop();
                      await _refresh();
                    }
                  },
                  child: const Text('Create'),
                ),
              ],
            );
          },
        );
      },
    );

    emailController.dispose();
    displayNameController.dispose();
  }

  Future<void> _showEditDialog(Map<String, dynamic> user, List<String> roles) async {
    final displayNameController = TextEditingController(text: '${user['display_name'] ?? ''}');
    final selectedRoles = ((user['roles'] as List<dynamic>? ?? <dynamic>[]).map((role) => '$role')).toSet();
    String status = '${user['status'] ?? 'active'}';

    await showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text('Edit ${user['email']}'),
              content: SizedBox(
                width: 520,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(controller: displayNameController, decoration: const InputDecoration(labelText: 'Display name', border: OutlineInputBorder())),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: status,
                      decoration: const InputDecoration(labelText: 'Status', border: OutlineInputBorder()),
                      items: const [
                        DropdownMenuItem(value: 'active', child: Text('Active')),
                        DropdownMenuItem(value: 'disabled', child: Text('Disabled')),
                      ],
                      onChanged: (value) => setDialogState(() => status = value ?? 'active'),
                    ),
                    const SizedBox(height: 12),
                    Align(alignment: Alignment.centerLeft, child: Text('Roles', style: Theme.of(context).textTheme.titleSmall)),
                    Wrap(
                      spacing: 8,
                      children: roles.map((role) {
                        return FilterChip(
                          label: Text(role),
                          selected: selectedRoles.contains(role),
                          onSelected: (selected) {
                            setDialogState(() {
                              if (selected) {
                                selectedRoles.add(role);
                              } else {
                                selectedRoles.remove(role);
                              }
                            });
                          },
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
                FilledButton(
                  onPressed: () async {
                    await _apiClient.updateUser(
                      userId: '${user['id']}',
                      displayName: displayNameController.text.trim(),
                      roles: selectedRoles.toList(),
                      status: status,
                    );
                    if (mounted) {
                      Navigator.of(context).pop();
                      await _refresh();
                    }
                  },
                  child: const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );

    displayNameController.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!AuthController.instance.isAdmin) {
      return const Center(child: Text('Admin role required.'));
    }

    return Padding(
      padding: const EdgeInsets.all(32),
      child: FutureBuilder<Map<String, dynamic>>(
        future: Future.wait([_usersFuture, _rolesFuture]).then((values) => <String, dynamic>{'users': values[0], 'roles': values[1]}),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return Center(child: Text('Unable to load users: ${snapshot.error}'));

          final usersResponse = snapshot.data?['users'] as Map<String, dynamic>? ?? <String, dynamic>{};
          final rolesResponse = snapshot.data?['roles'] as Map<String, dynamic>? ?? <String, dynamic>{};
          final users = (usersResponse['users'] as List<dynamic>? ?? <dynamic>[]).cast<Map<String, dynamic>>();
          final roles = (rolesResponse['roles'] as List<dynamic>? ?? <dynamic>[]).map((role) => '$role').toList();

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('User Admin', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        const Text('Manage local TrustVault users and role-based access controls.'),
                      ],
                    ),
                  ),
                  OutlinedButton.icon(onPressed: _refresh, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
                  const SizedBox(width: 12),
                  FilledButton.icon(onPressed: () => _showCreateDialog(roles), icon: const Icon(Icons.person_add_alt_1), label: const Text('New user')),
                ],
              ),
              const SizedBox(height: 24),
              Wrap(spacing: 8, runSpacing: 8, children: [
                Chip(label: Text('Users: ${users.length}')),
                Chip(label: Text('Roles: ${roles.length}')),
              ]),
              const SizedBox(height: 16),
              Expanded(
                child: Card(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: DataTable(
                      columns: const [
                        DataColumn(label: Text('Name')),
                        DataColumn(label: Text('Email')),
                        DataColumn(label: Text('Status')),
                        DataColumn(label: Text('Roles')),
                        DataColumn(label: Text('Last login')),
                        DataColumn(label: Text('Actions')),
                      ],
                      rows: users.map((user) {
                        final userRoles = (user['roles'] as List<dynamic>? ?? <dynamic>[]).join(', ');
                        return DataRow(cells: [
                          DataCell(Text('${user['display_name'] ?? '-'}')),
                          DataCell(Text('${user['email'] ?? '-'}')),
                          DataCell(Text('${user['status'] ?? '-'}')),
                          DataCell(SizedBox(width: 360, child: Text(userRoles, overflow: TextOverflow.ellipsis))),
                          DataCell(Text('${user['last_login_at'] ?? '-'}')),
                          DataCell(TextButton.icon(onPressed: () => _showEditDialog(user, roles), icon: const Icon(Icons.edit), label: const Text('Edit'))),
                        ]);
                      }).toList(),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
