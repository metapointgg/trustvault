import 'package:flutter/material.dart';

import '../assurance/assurance_overview_screen.dart';

class ExtractionScreen extends StatelessWidget {
  const ExtractionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const AssuranceOverviewScreen(kind: AssuranceKind.extraction);
  }
}
