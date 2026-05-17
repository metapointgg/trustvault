import 'package:go_router/go_router.dart';

import '../features/audit/audit_screen.dart';
import '../features/dashboard/dashboard_screen.dart';
import '../features/entities/entities_screen.dart';
import '../features/fits/fits_operations_screen.dart';
import '../features/jobs/jobs_screen.dart';
import '../features/licence/licence_screen.dart';
import '../features/search/search_screen.dart';
import '../shared/app_shell.dart';

final appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    ShellRoute(
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const DashboardScreen(),
        ),
        GoRoute(
          path: '/entities',
          builder: (context, state) => const EntitiesScreen(),
        ),
        GoRoute(
          path: '/search',
          builder: (context, state) => const SearchScreen(),
        ),
        GoRoute(
          path: '/fits',
          builder: (context, state) => const FitsOperationsScreen(),
        ),
        GoRoute(
          path: '/jobs',
          builder: (context, state) => const JobsScreen(),
        ),
        GoRoute(
          path: '/audit',
          builder: (context, state) => const AuditScreen(),
        ),
        GoRoute(
          path: '/licence',
          builder: (context, state) => const LicenceScreen(),
        ),
      ],
    ),
  ],
);
