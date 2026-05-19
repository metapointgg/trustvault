import 'package:flutter/material.dart';

import '../core/auth/auth_controller.dart';
import '../features/auth/login_screen.dart';
import 'app_router.dart';
import 'app_theme.dart';

class TrustVaultApp extends StatelessWidget {
  const TrustVaultApp({super.key});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: AuthController.instance,
      builder: (context, _) {
        if (!AuthController.instance.isAuthenticated) {
          return MaterialApp(
            title: 'TrustVault',
            debugShowCheckedModeBanner: false,
            theme: buildTrustVaultTheme(),
            home: const LoginScreen(),
          );
        }
        return MaterialApp.router(
          title: 'TrustVault',
          debugShowCheckedModeBanner: false,
          theme: buildTrustVaultTheme(),
          routerConfig: appRouter,
        );
      },
    );
  }
}
