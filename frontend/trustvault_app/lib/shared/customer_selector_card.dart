import 'package:flutter/material.dart';

import '../core/api/trustvault_api_client.dart';
import 'selected_customer.dart';

class CustomerSelectorCard extends StatefulWidget {
  const CustomerSelectorCard({
    super.key,
    this.title = 'Customer context',
    this.subtitle = 'Select a customer for this operation.',
    this.onChanged,
  });

  final String title;
  final String subtitle;
  final ValueChanged<Map<String, dynamic>?>? onChanged;

  @override
  State<CustomerSelectorCard> createState() => _CustomerSelectorCardState();
}

class _CustomerSelectorCardState extends State<CustomerSelectorCard> {
  final TrustVaultApiClient _apiClient = TrustVaultApiClient();
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _apiClient.getCustomers();
    SelectedCustomerController.refreshToken.addListener(_refresh);
  }

  @override
  void dispose() {
    SelectedCustomerController.refreshToken.removeListener(_refresh);
    super.dispose();
  }

  void _refresh() {
    setState(() {
      _future = _apiClient.getCustomers();
    });
  }

  Map<String, dynamic>? _findCustomer(List<dynamic> customers, String? externalId) {
    for (final item in customers) {
      final customer = item as Map<String, dynamic>;
      if (customer['external_id']?.toString() == externalId) return customer;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<List<dynamic>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const SizedBox(height: 56, child: Center(child: LinearProgressIndicator()));
            }
            if (snapshot.hasError) {
              return Row(
                children: [
                  Icon(Icons.error_outline, color: Theme.of(context).colorScheme.error),
                  const SizedBox(width: 12),
                  Expanded(child: Text('Unable to load customers: ${snapshot.error}')),
                  IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh)),
                ],
              );
            }
            final customers = (snapshot.data ?? <dynamic>[]).cast<dynamic>();
            if (customers.isEmpty) {
              return Row(
                children: [
                  const Icon(Icons.business_outlined),
                  const SizedBox(width: 12),
                  const Expanded(child: Text('No customers available. Upload a source folder to begin.')),
                  IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh)),
                ],
              );
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
                return Row(
                  children: [
                    const Icon(Icons.business_outlined),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(widget.title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 4),
                          Text(widget.subtitle),
                        ],
                      ),
                    ),
                    const SizedBox(width: 16),
                    SizedBox(
                      width: 360,
                      child: DropdownButtonFormField<String>(
                        value: selectedValue,
                        decoration: const InputDecoration(labelText: 'Customer', border: OutlineInputBorder()),
                        items: customers.map((item) {
                          final customer = item as Map<String, dynamic>;
                          final label = '${customer['display_name'] ?? customer['external_id']} (${customer['external_id']})';
                          return DropdownMenuItem<String>(
                            value: customer['external_id']?.toString(),
                            child: Text(label, overflow: TextOverflow.ellipsis),
                          );
                        }).toList(),
                        onChanged: (value) {
                          final customer = _findCustomer(customers, value);
                          SelectedCustomerController.select(customer);
                          widget.onChanged?.call(customer);
                        },
                      ),
                    ),
                    IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh), tooltip: 'Refresh customers'),
                  ],
                );
              },
            );
          },
        ),
      ),
    );
  }
}
