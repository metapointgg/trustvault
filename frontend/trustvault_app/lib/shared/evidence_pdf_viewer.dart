import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';

import '../core/api/trustvault_api_client.dart';

class EvidencePdfViewer extends StatelessWidget {
  const EvidencePdfViewer(
      {super.key, required this.apiClient, required this.evidenceObjectId});

  final TrustVaultApiClient apiClient;
  final String evidenceObjectId;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uint8List>(
      future: apiClient.downloadEvidenceBytes(evidenceObjectId),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text('Unable to load PDF evidence: ${snapshot.error}'),
            ),
          );
        }
        final bytes = snapshot.data;
        if (bytes == null || bytes.isEmpty) {
          return const Center(
              child: Text('No PDF data was returned for this evidence item.'));
        }
        return PdfViewer.data(bytes, sourceName: evidenceObjectId);
      },
    );
  }
}
