import 'package:go_router/go_router.dart';

import '../features/audit/audit_screen.dart';
import '../features/comparison/comparison_screen.dart';
import '../features/completeness/completeness_screen.dart';
import '../features/dashboard/dashboard_screen.dart';
import '../features/entities/entities_screen.dart';
import '../features/export/fits_export_screen.dart';
import '../features/extraction/extraction_screen.dart';
import '../features/feature_status/feature_status_screen.dart';
import '../features/fits/fits_operations_screen.dart';
import '../features/ingestion/source_folder_upload_screen.dart';
import '../features/integrity/integrity_screen.dart';
import '../features/jobs/jobs_screen.dart';
import '../features/licence/licence_screen.dart';
import '../features/retention/retention_screen.dart';
import '../features/search/search_screen.dart';
import '../shared/app_shell.dart';

final appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    ShellRoute(
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/', builder: (context, state) => const DashboardScreen()),
        GoRoute(
          path: '/health',
          builder: (context, state) => FeatureStatusScreen(
            title: 'Health',
            description: 'Operational status for API, database, storage, queue, worker, AI and OCR providers.',
            loader: (api) => api.getApiHealth(),
          ),
        ),
        GoRoute(path: '/comparison', builder: (context, state) => const ComparisonScreen()),
        GoRoute(path: '/customers', builder: (context, state) => const EntitiesScreen()),
        GoRoute(path: '/entities', builder: (context, state) => const EntitiesScreen()),
        GoRoute(path: '/search', builder: (context, state) => const SearchScreen()),
        GoRoute(path: '/completeness', builder: (context, state) => const CompletenessScreen()),
        GoRoute(
          path: '/rulesets',
          builder: (context, state) => FeatureStatusScreen(
            title: 'Rulesets',
            description: 'Required-evidence rulesets used by completeness reviews.',
            loader: (api) async => <String, dynamic>{'rulesets': await api.getRulesets()},
          ),
        ),
        GoRoute(path: '/ingestion', builder: (context, state) => const SourceFolderUploadScreen()),
        GoRoute(path: '/extraction', builder: (context, state) => const ExtractionScreen()),
        GoRoute(path: '/retention', builder: (context, state) => const RetentionScreen()),
        GoRoute(path: '/integrity', builder: (context, state) => const IntegrityScreen()),
        GoRoute(path: '/export', builder: (context, state) => const FitsExportScreen()),
        GoRoute(
          path: '/api',
          builder: (context, state) => FeatureStatusScreen(
            title: 'API',
            description: 'TrustVault API feature status and archive model.',
            loader: (api) => api.getApiStatus(),
          ),
        ),
        GoRoute(path: '/fits', builder: (context, state) => const FitsOperationsScreen()),
        GoRoute(path: '/jobs', builder: (context, state) => const JobsScreen()),
        GoRoute(path: '/audit', builder: (context, state) => const AuditScreen()),
        GoRoute(path: '/licence', builder: (context, state) => const LicenceScreen()),
      ],
    ),
  ],
);
