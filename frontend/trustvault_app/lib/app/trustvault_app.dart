import 'package:flutter/material.dart';

import 'app_router.dart';
import 'app_theme.dart';

class TrustVaultApp extends StatelessWidget {
  const TrustVaultApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'TrustVault',
      debugShowCheckedModeBanner: false,
      theme: buildTrustVaultTheme(),
      routerConfig: appRouter,
    );
  }
}
