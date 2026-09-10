import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:ygg/main.dart';

void main() {
  testWidgets('Splash screen muestra el logo y spinner', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: YggApp()));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
