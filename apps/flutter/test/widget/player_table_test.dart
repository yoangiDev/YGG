import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ygg/features/players/models/player.dart';
import 'package:ygg/features/players/providers/ddragon_provider.dart';
import 'package:ygg/features/players/widgets/player_table.dart';

Player _player({int id = 1, String gameName = 'Faker', String nickname = '', String tier = 'GOLD'}) =>
    Player(
      id: id, puuid: 'p$id', gameName: gameName, tagLine: 'EUW',
      region: 'EUW', nickname: nickname, role: 'MID', notes: '',
      tier: tier, rank: 'II', lp: 50, profileIconId: 0,
      wins: 10, losses: 5, winRate: 66.7,
    );

// Mockeamos los providers que hacen peticiones HTTP reales
Widget _wrap(Widget child) => ProviderScope(
  overrides: [
    ddragonVersionProvider.overrideWith((_) async => '16.10.1'),
    spellIconsProvider.overrideWith((_) async => {}),
  ],
  child: MaterialApp(
    theme: ThemeData.dark(),
    home: Scaffold(body: child),
  ),
);

void main() {
  group('PlayerTable', () {
    setUp(() {
      // PlayerRow está diseñado para pantalla ancha (desktop/web)
      TestWidgetsFlutterBinding.ensureInitialized();
    });

    testWidgets('muestra el nombre del jugador en la lista', (tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(_wrap(
        PlayerTable(
          players:         [_player(gameName: 'Faker')],
          isLoading:       false,
          searchQuery:     '',
          onSearchChanged: (_) {},
          onAddPlayer:     () {},
          onDelete:        (_) {},
          onRefresh:        (_) async {},
          onEditNotes:     (_, _) async {},
          onEditRole:      (_, _) async {},
        ),
      ));

      expect(find.text('Faker'), findsOneWidget);
    });

    testWidgets('muestra estado vacío cuando no hay jugadores', (tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(_wrap(
        PlayerTable(
          players:         const [],
          isLoading:       false,
          searchQuery:     '',
          onSearchChanged: (_) {},
          onAddPlayer:     () {},
          onDelete:        (_) {},
          onRefresh:        (_) async {},
          onEditNotes:     (_, _) async {},
          onEditRole:      (_, _) async {},
        ),
      ));

      expect(find.text('Sin Jugadores'), findsOneWidget);
    });

    testWidgets('filtra jugadores por búsqueda', (tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(_wrap(
        PlayerTable(
          players:         [_player(id: 1, gameName: 'Faker'), _player(id: 2, gameName: 'Caps')],
          isLoading:       false,
          searchQuery:     'Faker',
          onSearchChanged: (_) {},
          onAddPlayer:     () {},
          onDelete:        (_) {},
          onRefresh:        (_) async {},
          onEditNotes:     (_, _) async {},
          onEditRole:      (_, _) async {},
        ),
      ));

      expect(find.text('Faker'), findsOneWidget);
      expect(find.text('Caps'),  findsNothing);
    });

    testWidgets('muestra spinner cuando isLoading es true', (tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(_wrap(
        PlayerTable(
          players:         const [],
          isLoading:       true,
          searchQuery:     '',
          onSearchChanged: (_) {},
          onAddPlayer:     () {},
          onDelete:        (_) {},
          onRefresh:        (_) async {},
          onEditNotes:     (_, _) async {},
          onEditRole:      (_, _) async {},
        ),
      ));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('muestra "Sin resultados" cuando búsqueda no coincide', (tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(_wrap(
        PlayerTable(
          players:         [_player(gameName: 'Faker')],
          isLoading:       false,
          searchQuery:     'xyzxyz',
          onSearchChanged: (_) {},
          onAddPlayer:     () {},
          onDelete:        (_) {},
          onRefresh:        (_) async {},
          onEditNotes:     (_, _) async {},
          onEditRole:      (_, _) async {},
        ),
      ));

      expect(find.text('Sin resultados'), findsOneWidget);
    });
  });
}
