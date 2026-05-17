import 'package:flutter/foundation.dart';

class SelectedCustomerController {
  static final ValueNotifier<Map<String, dynamic>?> selected = ValueNotifier<Map<String, dynamic>?>(null);
  static final ValueNotifier<int> refreshToken = ValueNotifier<int>(0);

  static String? get externalId => selected.value?['external_id']?.toString();

  static String get displayLabel {
    final customer = selected.value;
    if (customer == null) return 'No customer selected';
    final displayName = customer['display_name'] ?? customer['external_id'];
    final externalId = customer['external_id'];
    return '$displayName ($externalId)';
  }

  static void select(Map<String, dynamic>? customer) {
    selected.value = customer;
  }

  static void requestRefresh() {
    refreshToken.value = refreshToken.value + 1;
  }
}
