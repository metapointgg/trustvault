import 'package:flutter/material.dart';

import '../assurance/assurance_overview_screen.dart';

class RetentionScreen extends StatelessWidget {
  const RetentionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const AssuranceOverviewScreen(kind: AssuranceKind.retention);
  }
}
