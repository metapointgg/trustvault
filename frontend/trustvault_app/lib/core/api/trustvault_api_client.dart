import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../auth/auth_controller.dart';

class TrustVaultApiClient {
  TrustVaultApiClient()
      : _dio = Dio(
          BaseOptions(
            baseUrl: const String.fromEnvironment('TRUSTVAULT_API_BASE_URL', defaultValue: 'http://localhost:8000'),
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 60),
          ),
        ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = AuthController.instance.accessToken;
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio _dio;

  String get baseUrl => _dio.options.baseUrl;

  Future<Map<String, dynamic>> login({required String email, required String verifier}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/auth/login', data: <String, dynamic>{'email': email, 'verifier': verifier});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getCurrentUser() async => _getMap('/api/v1/auth/me');
  Future<Map<String, dynamic>> getAvailableRoles() async => _getMap('/api/v1/auth/roles');
  Future<Map<String, dynamic>> getUsers() async => _getMap('/api/v1/auth/users');

  Future<Map<String, dynamic>> createUser({required String email, required String displayName, required List<String> roles, String status = 'active'}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/auth/users', data: <String, dynamic>{'email': email, 'display_name': displayName, 'roles': roles, 'status': status});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateUser({required String userId, String? displayName, List<String>? roles, String? status}) async {
    final response = await _dio.patch<Map<String, dynamic>>('/api/v1/auth/users/$userId', data: <String, dynamic>{if (displayName != null) 'display_name': displayName, if (roles != null) 'roles': roles, if (status != null) 'status': status});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getSettings() async => _getMap('/api/v1/settings');

  Future<Map<String, dynamic>> updateSettings(Map<String, dynamic> updates) async {
    final response = await _dio.patch<Map<String, dynamic>>('/api/v1/settings', data: <String, dynamic>{'updates': updates});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getDocumentClassificationSettings() async => _getMap('/api/v1/settings/document-classification');

  Future<Map<String, dynamic>> updateDocumentClassificationSettings(Map<String, dynamic> config) async {
    final response = await _dio.put<Map<String, dynamic>>('/api/v1/settings/document-classification', data: <String, dynamic>{'config': config});
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> getUncategorisedEvidence({int limit = 500}) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/evidence/uncategorised', queryParameters: <String, dynamic>{'limit': limit});
    return response.data ?? <dynamic>[];
  }

  Future<Map<String, dynamic>> updateEvidenceClassification({required List<String> evidenceObjectIds, required String documentType}) async {
    final response = await _dio.patch<Map<String, dynamic>>('/api/v1/evidence/classification', data: <String, dynamic>{'evidence_object_ids': evidenceObjectIds, 'document_type': documentType, 'rebuild_container': true, 'rebuild_index': true});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateCustomerInformation({required String customerId, required Map<String, dynamic> data}) async {
    final response = await _dio.patch<Map<String, dynamic>>('/api/v1/customers/$customerId/information', data: data);
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getAutoIngestionStatus() async => _getMap('/api/v1/auto-ingestion/status');

  Future<Map<String, dynamic>> scanAutoIngestionFolder() async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/auto-ingestion/scan');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> queueScanAutoIngestionFolder() async => queueAutoIngestionScan();

  Future<Map<String, dynamic>> queueAutoIngestionScan() async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/jobs', data: <String, dynamic>{'job_type': 'scan_drop_folder', 'payload': <String, dynamic>{'source': 'flutter_settings'}, 'created_by_user_id': 'local-user'});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getHealth() async => _getMap('/health');
  Future<Map<String, dynamic>> getApiHealth() async => _getMap('/api/v1/health');
  Future<Map<String, dynamic>> getDashboardSummary() async => _getMap('/api/v1/dashboard/summary');
  Future<Map<String, dynamic>> getApiStatus() async => _getMap('/api/v1/api/status');
  Future<Map<String, dynamic>> getArchiveStatus() async => _getMap('/api/v1/query/archive/status');
  Future<Map<String, dynamic>> getQueryScenarios() async => _getMap('/api/v1/query/scenarios');
  Future<Map<String, dynamic>> getLicenceStatus() async => _getMap('/api/v1/licence/status');
  Future<Map<String, dynamic>> getExportStatus() async => _getMap('/api/v1/export/status');
  Future<Map<String, dynamic>> getRetentionReport() async => _getMap('/api/v1/retention/report');
  Future<Map<String, dynamic>> getIntegritySummary() async => _getMap('/api/v1/integrity/summary');
  Future<Map<String, dynamic>> getExtractionSummary() async => _getMap('/api/v1/extraction/summary');

  Future<List<dynamic>> getCustomers({String? riskRating, String? jurisdiction, int? limit}) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/customers', queryParameters: <String, dynamic>{if (riskRating != null && riskRating.isNotEmpty) 'risk_rating': riskRating, if (jurisdiction != null && jurisdiction.isNotEmpty) 'jurisdiction': jurisdiction, if (limit != null) 'limit': limit});
    return response.data ?? <dynamic>[];
  }

  Future<List<dynamic>> getEntities() async => _getList('/api/v1/entities');
  Future<List<dynamic>> getAuditEvents() async => _getList('/api/v1/audit/events');
  Future<List<dynamic>> getJobs() async => _getList('/api/v1/jobs');
  Future<List<dynamic>> getRulesets() async => _getList('/api/v1/rulesets');

  Future<Map<String, dynamic>> getCompletenessSummary({String? riskRating, String? jurisdiction, String? entityExternalId, String? rulesetId, int limit = 1000}) async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/completeness/summary', queryParameters: <String, dynamic>{if (riskRating != null && riskRating.isNotEmpty && riskRating != 'All') 'risk_rating': riskRating, if (jurisdiction != null && jurisdiction.isNotEmpty && jurisdiction != 'All') 'jurisdiction': jurisdiction, if (entityExternalId != null && entityExternalId.isNotEmpty) 'entity_external_id': entityExternalId, if (rulesetId != null && rulesetId.isNotEmpty) 'ruleset_id': rulesetId, 'limit': limit});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> createRuleset({required String name, int version = 1, String status = 'draft', String? description}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/rulesets', data: <String, dynamic>{'name': name, 'version': version, 'status': status, if (description != null) 'description': description});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateRuleset({required String rulesetId, String? name, int? version, String? status, String? description}) async {
    final response = await _dio.patch<Map<String, dynamic>>('/api/v1/rulesets/$rulesetId', data: <String, dynamic>{if (name != null) 'name': name, if (version != null) 'version': version, if (status != null) 'status': status, if (description != null) 'description': description});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> deleteRuleset(String rulesetId) async {
    final response = await _dio.delete<Map<String, dynamic>>('/api/v1/rulesets/$rulesetId');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> createRulesetRule({required String rulesetId, required Map<String, dynamic> rule}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/rulesets/$rulesetId/rules', data: rule);
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> updateRulesetRule({required String rulesetId, required String ruleId, required Map<String, dynamic> rule}) async {
    final response = await _dio.patch<Map<String, dynamic>>('/api/v1/rulesets/$rulesetId/rules/$ruleId', data: rule);
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> deleteRulesetRule({required String rulesetId, required String ruleId}) async {
    final response = await _dio.delete<Map<String, dynamic>>('/api/v1/rulesets/$rulesetId/rules/$ruleId');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getCustomer(String customerId) async => _getMap('/api/v1/customers/$customerId');
  Future<Map<String, dynamic>> getCustomerEvidenceSummary(String customerId) async => _getMap('/api/v1/customers/$customerId/summary');
  Future<Map<String, dynamic>> getExtractionReport(String entityId) async => _getMap('/api/v1/extraction/entities/$entityId/report');
  Future<Map<String, dynamic>> getEntityRetention(String entityId) async => _getMap('/api/v1/retention/entities/$entityId');
  Future<Map<String, dynamic>> getEntityIntegrity(String entityId) async => _getMap('/api/v1/integrity/entities/$entityId');

  Future<Map<String, dynamic>> interpretQuery({required String query, String? entityExternalId, String mode = 'auto'}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/query/interpret', data: <String, dynamic>{'query': query, 'mode': mode, if (entityExternalId != null && entityExternalId.isNotEmpty) 'entity_external_id': entityExternalId});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> executeQuery({required String query, String? entityExternalId, int limit = 50, String mode = 'auto', bool includeAiSummary = false}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/query/execute', data: <String, dynamic>{'query': query, 'limit': limit, 'mode': mode, 'include_ai_summary': includeAiSummary, if (entityExternalId != null && entityExternalId.isNotEmpty) 'entity_external_id': entityExternalId});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> compareFitsVsDatabase(String entityId, {String? query}) async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/comparison/entities/$entityId/fits-vs-db', queryParameters: <String, dynamic>{if (query != null && query.isNotEmpty) 'query': query});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> evaluateCompleteness(String entityId, {String? rulesetId}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/completeness/entities/$entityId/evaluate', data: <String, dynamic>{if (rulesetId != null) 'ruleset_id': rulesetId});
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> getEntityEvidence(String entityId) async => _getList('/api/v1/entities/$entityId/evidence');
  Future<List<dynamic>> getEntityContainerVersions(String entityId) async => _getList('/api/v1/containers/entities/$entityId/versions');

  Future<Map<String, dynamic>> inspectEntityFits(String entityId) async => _getMap('/api/v1/fits/entities/$entityId/inspect');

  Future<Map<String, dynamic>> searchEntityFits(String entityId, String query) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/fits/entities/$entityId/search', data: <String, dynamic>{'query': query, 'limit': 50});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> searchFitsIndex({required String query, String? entityExternalId}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/fits/index/search', data: <String, dynamic>{'query': query, 'limit': 50, if (entityExternalId != null && entityExternalId.isNotEmpty) 'entity_external_id': entityExternalId});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> rebuildFitsIndex({String? entityExternalId}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/fits/index/rebuild', data: <String, dynamic>{if (entityExternalId != null) 'entity_external_id': entityExternalId});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> rebuildEntityContainer(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/containers/rebuild', data: <String, dynamic>{'entity_external_id': entityExternalId});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> validateContainerVersion(String containerVersionId) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/containers/versions/$containerVersionId/validate');
    return response.data ?? <String, dynamic>{};
  }

  String fitsDownloadUrl(String containerVersionId) => '$baseUrl/api/v1/export/containers/$containerVersionId/fits';
  String evidenceFileUrl(String evidenceObjectId) => '$baseUrl/api/v1/evidence/$evidenceObjectId/file';
  String evidenceDownloadUrl(String evidenceObjectId) => '$baseUrl/api/v1/evidence/$evidenceObjectId/download';

  Future<Uint8List> downloadFitsBytes(String containerVersionId) async {
    final response = await _dio.get<List<int>>('/api/v1/export/containers/$containerVersionId/fits', options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(response.data ?? <int>[]);
  }

  Future<Map<String, dynamic>> uploadSourceFolderZip({required String filename, required Uint8List bytes}) async {
    final formData = FormData.fromMap(<String, dynamic>{'file': MultipartFile.fromBytes(bytes, filename: filename)});
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/ingestion/source-folder/upload', data: formData);
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> uploadLicenceFile({required String filename, required Uint8List bytes}) async {
    final formData = FormData.fromMap(<String, dynamic>{'file': MultipartFile.fromBytes(bytes, filename: filename)});
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/licence/upload', data: formData);
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> queueEntityContainerRebuild(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/jobs', data: <String, dynamic>{'job_type': 'rebuild_entity_container', 'payload': <String, dynamic>{'entity_external_id': entityExternalId}, 'created_by_user_id': 'local-user'});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getEvidencePreview(String evidenceObjectId) async => _getMap('/api/v1/evidence/$evidenceObjectId/preview');

  Future<Map<String, dynamic>> searchEvidence(String query) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/evidence/search', data: <String, dynamic>{'query': query, 'limit': 50});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> ingestTextEvidence({required String entityExternalId, required String entityDisplayName, required String objectType, required String sourceSystem, required String filename, required String text}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/ingestion/text', data: <String, dynamic>{'entity_external_id': entityExternalId, 'entity_display_name': entityDisplayName, 'object_type': objectType, 'source_system': sourceSystem, 'filename': filename, 'text': text, 'metadata': <String, dynamic>{'created_from': 'flutter_app'}, 'rebuild_container': true, 'rebuild_index': true});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> createJob(String jobType) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/jobs', data: <String, dynamic>{'job_type': jobType, 'payload': <String, dynamic>{'source': 'flutter_app'}, 'created_by_user_id': 'local-user'});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> createTextIngestionJob({required String entityExternalId, required String entityDisplayName, required String filename, required String text}) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/jobs', data: <String, dynamic>{'job_type': 'ingest_text_evidence', 'payload': <String, dynamic>{'entity_external_id': entityExternalId, 'entity_display_name': entityDisplayName, 'object_type': 'document', 'source_system': 'flutter_queued_ingestion', 'filename': filename, 'text': text, 'metadata': <String, dynamic>{'created_from': 'flutter_app', 'ingestion_mode': 'queued'}}, 'created_by_user_id': 'local-user'});
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> _getMap(String path) async {
    final response = await _dio.get<Map<String, dynamic>>(path);
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> _getList(String path) async {
    final response = await _dio.get<List<dynamic>>(path);
    return response.data ?? <dynamic>[];
  }
}
