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

  Future<List<dynamic>> getAuditEvents() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/audit/events');
    return response.data ?? <dynamic>[];
  }
}
