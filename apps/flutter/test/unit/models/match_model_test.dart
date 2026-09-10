import 'package:flutter_test/flutter_test.dart';
import 'package:ygg/features/players/models/match_model.dart';

Map<String, dynamic> _baseJson({int kills = 5, int deaths = 2, int assists = 8,
    int duration = 1800, int totalCs = 180, bool win = true}) => {
  'match_id':          'EUW1_123',
  'champion':          'Ahri',
  'win':               win,
  'duration':          duration,
  'kills':             kills,
  'deaths':            deaths,
  'assists':           assists,
  'kill_participation': 65.0,
  'vision':            42,
  'total_cs':          totalCs,
  'item0': 3157, 'item1': 3089, 'item2': 4645,
  'item3': 3165, 'item4': 3135, 'item5': 3102, 'item6': 3364,
  'summoner1_id': 4,
  'summoner2_id': 14,
  'creation_time': '2026-05-01T20:00:00.000',
};

void main() {
  group('MatchModel.fromJson', () {
    test('parsea todos los campos correctamente', () {
      final m = MatchModel.fromJson(_baseJson());
      expect(m.matchId,   'EUW1_123');
      expect(m.champion,  'Ahri');
      expect(m.win,       true);
      expect(m.kills,     5);
      expect(m.deaths,    2);
      expect(m.assists,   8);
      expect(m.vision,    42);
      expect(m.totalCs,   180);
      expect(m.trinket,   3364);
    });

    test('usa 0 como valor por defecto para items ausentes', () {
      final json = _baseJson();
      json.remove('item0');
      final m = MatchModel.fromJson(json);
      expect(m.item0, 0);
    });
  });

  group('MatchModel.kdaValue', () {
    test('calcula KDA con muertes > 0', () {
      final m = MatchModel.fromJson(_baseJson(kills: 5, deaths: 2, assists: 8));
      expect(m.kdaValue, closeTo(6.5, 0.01));
    });

    test('devuelve kills+assists cuando deaths == 0', () {
      final m = MatchModel.fromJson(_baseJson(kills: 5, deaths: 0, assists: 8));
      expect(m.kdaValue, 13.0);
    });
  });

  group('MatchModel.csPerMin', () {
    test('calcula CS por minuto correctamente', () {
      final m = MatchModel.fromJson(_baseJson(totalCs: 180, duration: 1800));
      expect(m.csPerMin, closeTo(6.0, 0.01));
    });

    test('devuelve 0 si duration es 0', () {
      final m = MatchModel.fromJson(_baseJson(duration: 0));
      expect(m.csPerMin, 0.0);
    });
  });

  group('MatchModel.buildItems', () {
    test('devuelve los 6 primeros items (sin trinket)', () {
      final m = MatchModel.fromJson(_baseJson());
      expect(m.buildItems, [3157, 3089, 4645, 3165, 3135, 3102]);
      expect(m.trinket,    3364);
    });
  });
}
