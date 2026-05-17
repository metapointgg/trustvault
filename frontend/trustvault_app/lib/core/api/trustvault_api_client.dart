import 'package:dio/dio.dart';

class TrustVaultApiClient {
  TrustVaultApiClient()
      : _dio = Dio(
          BaseOptions(
            baseUrl: const String.fromEnvironment(
              'TRUSTVAULT_API_BASE_URL',
              defaultValue: 'http://localhost:8000',
            ),
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 30),
          ),
        );

  final Dio _dio;

  Future<Map<String, dynamic>> getHealth() async => _getMap('/health');
  Future<Map<String, dynamic>> getApiHealth() async => _getMap('/api/v1/health');
  Future<Map<String, dynamic>> getDashboardSummary() async => _getMap('/api/v1/dashboard/summary');
  Future<Map<String, dynamic>> getApiStatus() async => _getMap('/api/v1/api/status');
  Future<Map<String, dynamic>> getLicenceStatus() async => _getMap('/api/v1/licence/status');
  Future<Map<String, dynamic>> getExportStatus() async => _getMap('/api/v1/export/status');
  Future<Map<String, dynamic>> getRetentionReport() async => _getMap('/api/v1/retention/report');
  Future<Map<String, dynamic>> getIntegritySummary() async => _getMap('/api/v1/integrity/summary');

  Future<List<dynamic>> getCustomers() async => _getList('/api/v1/customers');
  Future<List<dynamic>> getEntities() async => _getList('/api/v1/entities');
  Future<List<dynamic>> getAuditEvents() async => _getList('/api/v1/audit/events');
  Future<List<dynamic>> getJobs() async => _getList('/api/v1/jobs');
  Future<List<dynamic>> getRulesets() async => _getList('/api/v1/rulesets');

  Future<Map<String, dynamic>> getCustomer(String customerId) async => _getMap('/api/v1/customers/$customerId');
  Future<Map<String, dynamic>> getExtractionReport(String entityId) async => _getMap('/api/v1/extraction/entities/$entityId/report');
  Future<Map<String, dynamic>> getEntityRetention(String entityId) async => _getMap('/api/v1/retention/entities/$entityId');
  Future<Map<String, dynamic>> getEntityIntegrity(String entityId) async => _getMap('/api/v1/integrity/entities/$entityId');
  Future<Map<String, dynamic>> compareFitsVsDatabase(String entityId, {String? query}) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/comparison/entities/$entityId/fits-vs-db',
      queryParameters: <String, dynamic>{if (query != null && query.isNotEmpty) 'query': query},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> evaluateCompleteness(String entityId, {String? rulesetId}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/completeness/entities/$entityId/evaluate',
      data: <String, dynamic>{if (rulesetId != null) 'ruleset_id': rulesetId},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> getEntityEvidence(String entityId) async => _getList('/api/v1/entities/$entityId/evidence');
  Future<List<dynamic>> getEntityContainerVersions(String entityId) async => _getList('/api/v1/containers/entities/$entityId/versions');

  Future<Map<String, dynamic>> inspectEntityFits(String entityId) async => _getMap('/api/v1/fits/entities/$entityId/inspect');

  Future<Map<String, dynamic>> searchEntityFits(String entityId, String query) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/fits/entities/$entityId/search',
      data: <String, dynamic>{'query': query, 'limit': 50},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> searchFitsIndex({required String query, String? entityExternalId}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/fits/index/search',
      data: <String, dynamic>{
        'query': query,
        'limit': 50,
        if (entityExternalId != null && entityExternalId.isNotEmpty) 'entity_external_id': entityExternalId,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> rebuildFitsIndex({String? entityExternalId}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/fits/index/rebuild',
      data: <String, dynamic>{if (entityExternalId != null) 'entity_external_id': entityExternalId},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> rebuildEntityContainer(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/containers/rebuild',
      data: <String, dynamic>{'entity_external_id': entityExternalId},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> validateContainerVersion(String containerVersionId) async {
    final response = await _dio.post<Map<String, dynamic>>('/api/v1/containers/versions/$containerVersionId/validate');
    return response.data ?? <String, dynamic>{};
  }

  Future<String> fitsDownloadUrl(String containerVersionId) async {
    return '${_dio.options.baseUrl}/api/v1/export/containers/$containerVersionId/fits';
  }

  Future<Map<String, dynamic>> queueEntityContainerRebuild(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/jobs',
      data: <String, dynamic>{
        'job_type': 'rebuild_entity_container',
        'payload': <String, dynamic>{'entity_external_id': entityExternalId},
        'created_by_user_id': 'local-user',
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getEvidencePreview(String evidenceObjectId) async => _getMap('/api/v1/evidence/$evidenceObjectId/preview');

  Future<Map<String, dynamic>> searchEvidence(String query) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/evidence/search',
      data: <String, dynamic>{'query': query, 'limit': 50},
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> ingestTextEvidence({
    required String entityExternalId,
    required String entityDisplayName,
    required String objectType,
    required String sourceSystem,
    required String filename,
    required String text,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ingestion/text',
      data: <String, dynamic>{
        'entity_external_id': entityExternalId,
        'entity_display_name': entityDisplayName,
        'object_type': objectType,
        'source_system': sourceSystem,
        'filename': filename,
        'text': text,
        'metadata': <String, dynamic>{'created_from': 'flutter_app'},
        'rebuild_container': true,
        'rebuild_index': true,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> createJob(String jobType) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/jobs',
      data: <String, dynamic>{
        'job_type': jobType,
        'payload': <String, dynamic>{'source': 'flutter_app'},
        'created_by_user_id': 'local-user',
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> createTextIngestionJob({
    required String entityExternalId,
    required String entityDisplayName,
    required String filename,
    required String text,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/jobs',
      data: <String, dynamic>{
        'job_type': 'ingest_text_evidence',
        'payload': <String, dynamic>{
          'entity_external_id': entityExternalId,
          'entity_display_name': entityDisplayName,
          'object_type': 'document',
          'source_system': 'flutter_queued_ingestion',
          'filename': filename,
          'text': text,
          'metadata': <String, dynamic>{'created_from': 'flutter_app', 'ingestion_mode': 'queued'},
        },
        'created_by_user_id': 'local-user',
      },
    );
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
