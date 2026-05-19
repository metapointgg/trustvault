import 'package:flutter/material.dart';

import '../assurance/assurance_overview_screen.dart';

class IntegrityScreen extends StatelessWidget {
  const IntegrityScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const AssuranceOverviewScreen(kind: AssuranceKind.integrity);
  }
}
