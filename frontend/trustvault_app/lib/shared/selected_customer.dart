import 'package:flutter/foundation.dart';

class SelectedCustomerController {
  static final ValueNotifier<Map<String, dynamic>?> selected =
      ValueNotifier<Map<String, dynamic>?>(null);
  static final ValueNotifier<int> refreshToken = ValueNotifier<int>(0);
  static bool openSearchForSelectedEntity = false;

  static String? get externalId => selected.value?['external_id']?.toString();

  static String get displayLabel {
    final entity = selected.value;
    if (entity == null) return 'No entity selected';
    final displayName = entity['display_name'] ?? entity['external_id'];
    final externalId = entity['external_id'];
    return '$displayName ($externalId)';
  }

  static void select(Map<String, dynamic>? entity) {
    selected.value = entity;
  }

  static void requestSearchForSelectedEntity(Map<String, dynamic> entity) {
    selected.value = entity;
    openSearchForSelectedEntity = true;
  }

  static bool consumeSearchForSelectedEntityRequest() {
    final value = openSearchForSelectedEntity;
    openSearchForSelectedEntity = false;
    return value;
  }

  static void requestRefresh() {
    refreshToken.value = refreshToken.value + 1;
  }
}
