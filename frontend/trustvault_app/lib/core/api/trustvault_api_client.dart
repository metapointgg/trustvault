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
            receiveTimeout: const Duration(seconds: 20),
          ),
        );

  final Dio _dio;

  Future<Map<String, dynamic>> getHealth() async {
    final response = await _dio.get<Map<String, dynamic>>('/health');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getDashboardSummary() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/dashboard/summary');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> getLicenceStatus() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/licence/status');
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> getEntities() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/entities');
    return response.data ?? <dynamic>[];
  }

  Future<List<dynamic>> getEntityEvidence(String entityId) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/entities/$entityId/evidence');
    return response.data ?? <dynamic>[];
  }

  Future<List<dynamic>> getEntityContainerVersions(String entityId) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/containers/entities/$entityId/versions');
    return response.data ?? <dynamic>[];
  }

  Future<Map<String, dynamic>> inspectEntityFits(String entityId) async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/fits/entities/$entityId/inspect');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> searchEntityFits(String entityId, String query) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/fits/entities/$entityId/search',
      data: <String, dynamic>{
        'query': query,
        'limit': 50,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> searchFitsIndex({
    required String query,
    String? entityExternalId,
  }) async {
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
      data: <String, dynamic>{
        if (entityExternalId != null) 'entity_external_id': entityExternalId,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> rebuildEntityContainer(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/containers/rebuild',
      data: <String, dynamic>{
        'entity_external_id': entityExternalId,
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> validateContainerVersion(String containerVersionId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/containers/versions/$containerVersionId/validate',
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> queueEntityContainerRebuild(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/jobs',
      data: <String, dynamic>{
        'job_type': 'rebuild_entity_container',
        'payload': <String, dynamic>{
          'entity_external_id': entityExternalId,
        },
        'created_by_user_id': 'local-user',
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> createRegulatorPack(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/exports/regulator-pack',
      data: <String, dynamic>{
        'entity_external_id': entityExternalId,
        'created_by_user_id': 'local-user',
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> queueRegulatorPackExport(String entityExternalId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/jobs',
      data: <String, dynamic>{
        'job_type': 'export_regulator_pack',
        'payload': <String, dynamic>{
          'entity_external_id': entityExternalId,
          'created_by_user_id': 'local-user',
        },
        'created_by_user_id': 'local-user',
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> getEntityExportPacks(String entityId) async {
    final response = await _dio.get<List<dynamic>>('/api/v1/exports/entities/$entityId/packs');
    return response.data ?? <dynamic>[];
  }

  Future<Map<String, dynamic>> getEvidencePreview(String evidenceObjectId) async {
    final response = await _dio.get<Map<String, dynamic>>('/api/v1/evidence/$evidenceObjectId/preview');
    return response.data ?? <String, dynamic>{};
  }

  Future<Map<String, dynamic>> searchEvidence(String query) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/evidence/search',
      data: <String, dynamic>{
        'query': query,
        'limit': 50,
      },
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
        'metadata': <String, dynamic>{
          'created_from': 'flutter_app',
        },
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> getJobs() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/jobs');
    return response.data ?? <dynamic>[];
  }

  Future<Map<String, dynamic>> createJob(String jobType) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/jobs',
      data: <String, dynamic>{
        'job_type': jobType,
        'payload': <String, dynamic>{
          'source': 'flutter_app',
        },
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
          'metadata': <String, dynamic>{
            'created_from': 'flutter_app',
            'ingestion_mode': 'queued',
          },
        },
        'created_by_user_id': 'local-user',
      },
    );
    return response.data ?? <String, dynamic>{};
  }

  Future<List<dynamic>> getAuditEvents() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/audit/events');
    return response.data ?? <dynamic>[];
  }
}
