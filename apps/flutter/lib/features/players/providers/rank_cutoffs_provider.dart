import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/rank_cutoffs_model.dart';

const _storageKey = 'rank_cutoffs_cache_v3';
const rankCutoffsRefreshInterval = Duration(hours: 4);

const kSupportedRegions = [
  'EUW', 'EUNE', 'TR', 'RU', 'NA', 'LAN', 'LAS', 'BR',
];

class RankCutoffsNotifier extends StateNotifier<Map<String, RankCutoffs>> {
  RankCutoffsNotifier() : super({}) {
    _loadFromCache();
  }

  Future<void> _loadFromCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_storageKey);
      if (raw == null) return;

      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      final restored = <String, RankCutoffs>{};
      for (final entry in decoded.entries) {
        restored[entry.key] = RankCutoffs.fromJson(
          Map<String, dynamic>.from(entry.value as Map),
        );
      }
      state = restored;
    } catch (_) {
      // Ignore corrupt cache.
    }
  }

  Future<void> _persist() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final payload = {
        for (final entry in state.entries)
          entry.key: entry.value.toJson(),
      };
      await prefs.setString(_storageKey, jsonEncode(payload));
    } catch (_) {
      // Non-critical.
    }
  }

  bool isStale(RankCutoffs cutoffs) {
    return DateTime.now().difference(cutoffs.fetchedAt) >= rankCutoffsRefreshInterval;
  }

  DateTime nextRefreshAt(RankCutoffs cutoffs) {
    return cutoffs.fetchedAt.add(rankCutoffsRefreshInterval);
  }

  Future<bool> refreshRegion(String region, {bool force = false}) async {
    final key = region.toUpperCase();
    final cached = state[key];
    if (!force && cached != null && !isStale(cached)) {
      return true;
    }

    try {
      final res = await ApiClient.instance.dio.get(
        Endpoints.rankCutoffs,
        queryParameters: {
          'region':  key,
          'refresh': force || cached == null || isStale(cached),
        },
      );
      final cutoffs = RankCutoffs.fromJson(
        Map<String, dynamic>.from(res.data as Map),
      );
      state = {...state, cutoffs.region.toUpperCase(): cutoffs};
      await _persist();
      return true;
    } catch (_) {
      return cached != null;
    }
  }

  Future<void> refreshRegions(
    Iterable<String> regions, {
    bool force = false,
  }) async {
    final unique = regions.map((r) => r.toUpperCase()).toSet();
    for (final region in unique) {
      await refreshRegion(region, force: force);
    }
  }

  Future<void> refreshRegionsIfStale(Iterable<String> regions) async {
    final unique = regions.map((r) => r.toUpperCase()).toSet();
    for (final region in unique) {
      await refreshRegion(region);
    }
  }
}

final rankCutoffsProvider =
    StateNotifierProvider<RankCutoffsNotifier, Map<String, RankCutoffs>>(
  (ref) => RankCutoffsNotifier(),
);

RankCutoffs? rankCutoffsForRegion(
  Map<String, RankCutoffs> cutoffs,
  String region,
) =>
    cutoffs[region.toUpperCase()];
