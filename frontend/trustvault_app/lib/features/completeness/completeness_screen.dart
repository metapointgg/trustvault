import 'package:flutter/material.dart';

import '../assurance/assurance_overview_screen.dart';

class CompletenessScreen extends StatelessWidget {
  const CompletenessScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const AssuranceOverviewScreen(kind: AssuranceKind.completeness);
  }
}
