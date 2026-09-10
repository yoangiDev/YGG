import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:ygg/features/players/models/player.dart';
import 'package:ygg/features/players/providers/players_provider.dart';
import 'package:ygg/features/players/repositories/player_repository.dart';

class MockPlayerRepository extends Mock implements PlayerRepository {}

Player _fakePlayer({int id = 1, String gameName = 'Faker'}) => Player(
  id:            id,
  puuid:         'puuid$id',
  gameName:      gameName,
  tagLine:       'EUW',
  region:        'EUW',
  nickname:      '',
  role:          'ALL',
  notes:         '',
  tier:          'GOLD',
  rank:          'II',
  lp:            50,
  profileIconId: 0,
  wins:          10,
  losses:        5,
  winRate:       66.7,
);

void main() {
  setUpAll(() {
    registerFallbackValue(
      const PlayerCreateData(gameName: 'x', tagLine: 'x', region: 'x'),
    );
  });

  late MockPlayerRepository mockRepo;
  late ProviderContainer container;

  setUp(() {
    mockRepo  = MockPlayerRepository();
    container = ProviderContainer(
      overrides: [
        playerRepositoryProvider.overrideWithValue(mockRepo),
      ],
    );
    addTearDown(container.dispose);
  });

  group('PlayersNotifier.build (carga inicial)', () {
    test('carga la lista desde el repositorio', () async {
      final players = [_fakePlayer(id: 1), _fakePlayer(id: 2)];
      when(() => mockRepo.list()).thenAnswer((_) async => players);

      final result = await container.read(playersProvider.future);
      expect(result.length, 2);
      expect(result.first.id, 1);
    });

    test('propaga el error si el repositorio falla', () async {
      when(() => mockRepo.list()).thenThrow(Exception('Error de red'));

      await expectLater(
        container.read(playersProvider.future),
        throwsA(isA<Exception>()),
      );
    });
  });

  group('PlayersNotifier.deletePlayer', () {
    test('elimina el jugador de la lista en el estado', () async {
      final players = [_fakePlayer(id: 1), _fakePlayer(id: 2)];
      when(() => mockRepo.list()).thenAnswer((_) async => players);
      when(() => mockRepo.delete(1)).thenAnswer((_) async {});

      await container.read(playersProvider.future);
      final err = await container.read(playersProvider.notifier).deletePlayer(1);

      expect(err, isNull);
      final remaining = container.read(playersProvider).valueOrNull;
      expect(remaining?.length, 1);
      expect(remaining?.first.id, 2);
    });

    test('devuelve mensaje de error si el repositorio lanza excepción', () async {
      when(() => mockRepo.list()).thenAnswer((_) async => [_fakePlayer()]);
      when(() => mockRepo.delete(any())).thenThrow(Exception('fallo'));

      await container.read(playersProvider.future);
      final err = await container.read(playersProvider.notifier).deletePlayer(1);

      expect(err, isNotNull);
    });
  });

  group('PlayersNotifier.addPlayer', () {
    test('añade el nuevo jugador al principio de la lista', () async {
      final existing = [_fakePlayer(id: 1)];
      final newPlayer = _fakePlayer(id: 2, gameName: 'Caps');
      when(() => mockRepo.list()).thenAnswer((_) async => existing);
      when(() => mockRepo.create(any())).thenAnswer((_) async => newPlayer);

      await container.read(playersProvider.future);
      final err = await container.read(playersProvider.notifier).addPlayer(
        const PlayerCreateData(gameName: 'Caps', tagLine: 'EUW', region: 'EUW'),
      );

      expect(err, isNull);
      final updated = container.read(playersProvider).valueOrNull;
      expect(updated?.first.id, 2);
      expect(updated?.length, 2);
    });
  });
}
