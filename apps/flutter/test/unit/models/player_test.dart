import 'package:flutter_test/flutter_test.dart';
import 'package:ygg/features/players/models/player.dart';

void main() {
  group('Player.fromJson', () {
    const json = {
      'id': 1,
      'puuid': 'abc123',
      'game_name': 'Faker',
      'tag_line': 'KR1',
      'region': 'EUW',
      'nickname': 'El Diablo',
      'role': 'MID',
      'notes': 'Buen control de mapa',
      'tier': 'CHALLENGER',
      'rank': 'I',
      'lp': 1200,
      'profile_icon_id': 4567,
      'wins': 80,
      'losses': 20,
      'win_rate': 80.0,
    };

    test('parsea todos los campos correctamente', () {
      final player = Player.fromJson(json);
      expect(player.id,            1);
      expect(player.puuid,         'abc123');
      expect(player.gameName,      'Faker');
      expect(player.tagLine,       'KR1');
      expect(player.region,        'EUW');
      expect(player.nickname,      'El Diablo');
      expect(player.role,          'MID');
      expect(player.notes,         'Buen control de mapa');
      expect(player.tier,          'CHALLENGER');
      expect(player.rank,          'I');
      expect(player.lp,            1200);
      expect(player.profileIconId, 4567);
      expect(player.wins,          80);
      expect(player.losses,        20);
      expect(player.winRate,       80.0);
    });

    test('usa valores por defecto para campos opcionales nulos', () {
      final minimal = Player.fromJson({
        'id': 2, 'puuid': 'x', 'game_name': 'Test', 'tag_line': 'EUW',
        'region': 'EUW',
      });
      expect(minimal.nickname,      '');
      expect(minimal.role,          'ALL');
      expect(minimal.notes,         '');
      expect(minimal.tier,          '');
      expect(minimal.rank,          '');
      expect(minimal.lp,            0);
      expect(minimal.profileIconId, 0);
      expect(minimal.wins,          0);
      expect(minimal.losses,        0);
      expect(minimal.winRate,       0.0);
    });
  });

  group('Player.riotId', () {
    test('devuelve gameName#tagLine', () {
      final player = Player.fromJson({
        'id': 1, 'puuid': 'x', 'game_name': 'Faker', 'tag_line': 'KR1', 'region': 'EUW',
      });
      expect(player.riotId, 'Faker#KR1');
    });
  });

  group('Player.gamesPlayed', () {
    test('suma wins y losses', () {
      final player = Player.fromJson({
        'id': 1, 'puuid': 'x', 'game_name': 'X', 'tag_line': 'X', 'region': 'EUW',
        'wins': 60, 'losses': 40,
      });
      expect(player.gamesPlayed, 100);
    });
  });

  group('Player.copyWith', () {
    final base = Player.fromJson({
      'id': 1, 'puuid': 'abc', 'game_name': 'Test', 'tag_line': 'EUW',
      'region': 'EUW', 'notes': 'original', 'tier': 'GOLD', 'lp': 50,
    });

    test('actualiza solo el campo indicado', () {
      final updated = base.copyWith(notes: 'nueva nota');
      expect(updated.notes,    'nueva nota');
      expect(updated.gameName, 'Test');
      expect(updated.tier,     'GOLD');
    });

    test('los demás campos no cambian', () {
      final updated = base.copyWith(lp: 100);
      expect(updated.lp,    100);
      expect(updated.notes, 'original');
    });
  });
}
