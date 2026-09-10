import '../../../../core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import '../../models/match_model.dart';

class CalculatedMetric {
  final String label;
  final String value;
  final String status;
  final List<double>? sparkData;

  CalculatedMetric({
    required this.label,
    required this.value,
    required this.status,
    this.sparkData,
  });
}

String checkStatus(String key, double val, String role) {
  final k = key.toLowerCase().replaceAll('_', ' ').trim();
  final r = role.toUpperCase();

  if (k == "kda") {
    if (val >= 5.5) return "excellent";
    if (val >= 4.2) return "good";
    if (val >= 3.2) return "normal";
    return "bad";
  } else if (k == "cs/min" || k == "cs min") {
    if (val >= 10.0) return "excellent";
    if (val >= 8.8) return "good";
    if (val >= 7.8) return "normal";
    return "bad";
  } else if (k == "deaths" || k == "deaths/game") {
    if (val <= 2.5) return "excellent";
    if (val <= 3.5) return "good";
    if (val <= 4.2) return "normal";
    return "bad";
  } else if (k == "solo kills") {
    if (val >= 2.2) return "excellent";
    if (val >= 1.2) return "good";
    if (val >= 0.6) return "normal";
    return "bad";
  } else if (k == "solo deaths") {
    if (val <= 0.3) return "excellent";
    if (val <= 0.6) return "good";
    if (val <= 1.0) return "normal";
    return "bad";
  } else if (k.contains("gold diff")) {
    if (val >= 600) return "excellent";
    if (val >= 250) return "good";
    if (val >= 0) return "normal";
    return "bad";
  } else if (k.contains("cs diff")) {
    if (val >= 15) return "excellent";
    if (val >= 8) return "good";
    if (val >= 2) return "normal";
    return "bad";
  } else if (k == "obj vision" || k.contains("objective prep") || k == "obj prep vision") {
    if (val >= 6.5) return "excellent";
    if (val >= 4.5) return "good";
    if (val >= 3.0) return "normal";
    return "bad";
  } else if (k == "dmg/min" || k == "dmg min" || k == "damage/min") {
    if (val >= 750.0) return "excellent";
    if (val >= 600.0) return "good";
    if (val >= 450.0) return "normal";
    return "bad";
  } else if (k == "gold/min" || k == "gold min") {
    if (val >= 440.0) return "excellent";
    if (val >= 380.0) return "good";
    if (val >= 320.0) return "normal";
    return "bad";
  } else if (k.contains("vision") || k == "vision score/min" || k == "vision min") {
    if (val < 10.0) {
      if (val >= 2.5) return "excellent";
      if (val >= 2.0) return "good";
      if (val >= 1.5) return "normal";
      return "bad";
    } else {
      if (val >= 75.0) return "excellent";
      if (val >= 60.0) return "good";
      if (val >= 45.0) return "normal";
      return "bad";
    }
  } else if (k.contains("kp") || k.contains("participation")) {
    if (val >= 72.0) return "excellent";
    if (val >= 62.0) return "good";
    if (val >= 52.0) return "normal";
    return "bad";
  } else if (k == "struct dmg" || k == "daño a estructuras") {
    if (val >= 9000) return "excellent";
    if (val >= 7000) return "good";
    if (val >= 5000) return "normal";
    return "bad";
  } else if (k == "obj control" || k == "control objetivos") {
    if (val >= 65.0) return "excellent";
    if (val >= 55.0) return "good";
    if (val >= 45.0) return "normal";
    return "bad";
  } else if (k == "dragon setup" || k == "dragon setup rate") {
    if (val >= 75.0) return "excellent";
    if (val >= 60.0) return "good";
    if (val >= 45.0) return "normal";
    return "bad";
  } else if (k == "first dragon" || k == "first dragons") {
    if (val >= 60.0) return "excellent";
    if (val >= 50.0) return "good";
    if (val >= 40.0) return "normal";
    return "bad";
  } else if (k == "void grubs") {
    if (val >= 60.0) return "excellent";
    if (val >= 50.0) return "good";
    if (val >= 40.0) return "normal";
    return "bad";
  } else if (k == "rift herald" || k == "rift heralds" || k == "herald") {
    if (val >= 60.0) return "excellent";
    if (val >= 50.0) return "good";
    if (val >= 40.0) return "normal";
    return "bad";
  } else if (k == "enemy jg" || k.contains("camps cleared")) {
    if (val >= 16) return "excellent";
    if (val >= 11) return "good";
    if (val >= 7) return "normal";
    return "bad";
  } else if (k == "pink wards" || k == "control wards" || k.contains("pink")) {
    if (r == "SUPPORT") {
      if (val >= 9) return "excellent";
      if (val >= 7) return "good";
      if (val >= 5) return "normal";
      return "bad";
    } else if (r == "JUNGLE") {
      if (val >= 7) return "excellent";
      if (val >= 5) return "good";
      if (val >= 3) return "normal";
      return "bad";
    } else {
      if (val >= 5) return "excellent";
      if (val >= 3) return "good";
      if (val >= 2) return "normal";
      return "bad";
    }
  } else if (k == "laning deaths") {
    if (val <= 0.8) return "excellent";
    if (val <= 1.3) return "good";
    if (val <= 2.0) return "normal";
    return "bad";
  } else if (k == "post-14 deaths") {
    if (val <= 1.2) return "excellent";
    if (val <= 2.0) return "good";
    if (val <= 3.0) return "normal";
    return "bad";
  } else if (k == "lane deaths" || k.contains("laning (pre-14)")) {
    if (val <= 25.0) return "excellent";
    if (val <= 40.0) return "good";
    if (val <= 55.0) return "normal";
    return "bad";
  } else if (k == "side deaths" || k.contains("side (post-14)")) {
    if (val <= 18.0) return "excellent";
    if (val <= 30.0) return "good";
    if (val <= 45.0) return "normal";
    return "bad";
  } else if (k == "roaming" || k == "roaming proactivity") {
    if (val >= 4.5) return "excellent";
    if (val >= 3.0) return "good";
    if (val >= 1.8) return "normal";
    return "bad";
  } else if (k == "efficiency" || k == "efficiency ratio" || k == "dmg share / gold share") {
    if (val >= 1.25) return "excellent";
    if (val >= 1.05) return "good";
    if (val >= 0.85) return "normal";
    return "bad";
  } else if (k == "dmg/gold" || k == "dmg gold") {
    if (val >= 1.25) return "excellent";
    if (val >= 1.05) return "good";
    if (val >= 0.85) return "normal";
    return "bad";
  } else if (k == "dmg share" || k == "damage share") {
    if (val >= 33.0) return "excellent";
    if (val >= 29.0) return "good";
    if (val >= 25.0) return "normal";
    return "bad";
  } else if (k == "early gank deaths" || k.contains("death by early ganks") || k == "early ganks") {
    if (val <= 0.10) return "excellent";
    if (val <= 0.25) return "good";
    if (val <= 0.45) return "normal";
    return "bad";
  } else if (k == "quest time" || k == "quest_time") {
    if (val <= 660) return "excellent";
    if (val <= 720) return "good";
    if (val <= 900) return "normal";
    return "bad";
  }
  return "normal";
}

/// Mapeo semántico completo: distingue métricas negativas (muertes)
/// de las positivas para aplicar el color correcto en cada caso.
Color getStatColor(String metricKey, String status) {
  final key = metricKey.toLowerCase();
  final s   = status.toLowerCase();

  final isNegative = key.contains('death') || key.contains('muertes');

  if (isNegative) {
    switch (s) {
      case 'bad':       return kStatRed;
      case 'normal':    return kStatGray;
      case 'good':      return kStatBlue;
      case 'excellent': return kStatGold;
      default:          return kStatGray;
    }
  }

  switch (s) {
    case 'excellent': return kStatGold;
    case 'good':      return kStatBlue;
    case 'normal':    return kStatGreen;
    case 'bad':       return kStatGray;
    case 'neutral':
    default:          return kForeground;
  }
}

/// Alias sin clave de métrica (métricas positivas por defecto).
Color getStatusColor(String status) => getStatColor('', status);

double _avg(Iterable<num> vals) {
  if (vals.isEmpty) return 0.0;
  double sum = 0.0;
  for (final v in vals) {
    sum += v;
  }
  return sum / vals.length;
}

List<double>? _spark(List<double> vals) => vals.length > 1 ? vals : null;

List<CalculatedMetric> buildCalculatedMetrics({
  required List<MatchModel> allMatches,
  required String activeRole,
  String? champion,
}) {
  final filtered = [...(champion != null
      ? allMatches.where((m) => m.champion == champion)
      : allMatches)]
    ..sort((a, b) => a.creationTime.compareTo(b.creationTime));

  final n = filtered.length;
  if (n == 0) return const [];

  final List<CalculatedMetric> metrics = [];

  metrics.add(CalculatedMetric(label: 'GAMES', value: '$n', status: 'neutral'));

  final winrate = filtered.where((m) => m.win).length / n * 100;
  metrics.add(CalculatedMetric(
    label: 'WINRATE',
    value: '${winrate.toStringAsFixed(1)}%',
    status: winrate >= 55 ? 'excellent' : winrate >= 50 ? 'good' : winrate >= 45 ? 'normal' : 'bad',
    sparkData: _spark(filtered.map((m) => m.win ? 1.0 : 0.0).toList()),
  ));

  final questGames = filtered.where((m) => m.questCompletionTime != null).toList();
  if (questGames.isNotEmpty) {
    final avgQuestSec = _avg(questGames.map((m) => m.questCompletionTime!));
    metrics.add(CalculatedMetric(
      label: 'QUEST TIME',
      value: MatchModel.formatQuestTime(avgQuestSec.round()),
      status: checkStatus('quest_time', avgQuestSec, activeRole),
      sparkData: _spark(questGames.map((m) => m.questCompletionTime!.toDouble()).toList()),
    ));
  }

  if (activeRole == 'TOP') {
    final avgGold14 = _avg(filtered.map((m) => m.goldDiff14).whereType<int>());
    final avgCs14 = _avg(filtered.map((m) => m.csDiff14).whereType<int>());
    final avgSoloKills = _avg(filtered.map((m) => m.soloKills));
    final avgSoloDeaths = _avg(filtered.map((m) => m.deathEvents.where((d) => d.assistingParticipantIds.isEmpty).length));
    final avgDmgShare = _avg(filtered.map((m) => m.damageShare));
    final avgGoldShare = _avg(filtered.map((m) => m.goldShare));
    final eff = avgGoldShare > 0 ? avgDmgShare / avgGoldShare : 0.0;
    final avgStructDmg = _avg(filtered.map((m) => m.damageStructures));
    final avgKda = _avg(filtered.map((m) => m.kdaValue));
    final avgCsMin = _avg(filtered.map((m) => m.csPerMin));
    final avgDeaths = _avg(filtered.map((m) => m.deaths));
    final avgEarlyGanks = _avg(filtered.map((m) => m.earlyGankDeaths));

    metrics.addAll([
      CalculatedMetric(label: 'GOLD DIFF @14', value: '${avgGold14 >= 0 ? "+" : ""}${avgGold14.toStringAsFixed(0)}g', status: checkStatus('gold_diff_14', avgGold14, activeRole), sparkData: _spark(filtered.map((m) => (m.goldDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'CS DIFF @14', value: '${avgCs14 >= 0 ? "+" : ""}${avgCs14.toStringAsFixed(1)}', status: checkStatus('cs_diff_14', avgCs14, activeRole), sparkData: _spark(filtered.map((m) => (m.csDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'SOLO KILLS / GAME', value: avgSoloKills.toStringAsFixed(1), status: checkStatus('solo_kills', avgSoloKills, activeRole), sparkData: _spark(filtered.map((m) => m.soloKills.toDouble()).toList())),
      CalculatedMetric(label: 'SOLO DEATHS / GAME', value: avgSoloDeaths.toStringAsFixed(1), status: checkStatus('solo_deaths', avgSoloDeaths, activeRole), sparkData: _spark(filtered.map((m) => m.deathEvents.where((d) => d.assistingParticipantIds.isEmpty).length.toDouble()).toList())),
      CalculatedMetric(label: 'EFFICIENCY (DMG/GOLD)', value: eff.toStringAsFixed(2), status: checkStatus('efficiency', eff, activeRole), sparkData: _spark(filtered.map((m) => m.goldShare > 0 ? m.damageShare / m.goldShare : 0.0).toList())),
      CalculatedMetric(label: 'DAMAGE TO STRUCTURES', value: avgStructDmg.toStringAsFixed(0), status: checkStatus('struct_dmg', avgStructDmg, activeRole), sparkData: _spark(filtered.map((m) => m.damageStructures.toDouble()).toList())),
      CalculatedMetric(label: 'KDA', value: avgKda.toStringAsFixed(2), status: checkStatus('kda', avgKda, activeRole), sparkData: _spark(filtered.map((m) => m.kdaValue).toList())),
      CalculatedMetric(label: 'CS / MIN', value: avgCsMin.toStringAsFixed(1), status: checkStatus('cs_min', avgCsMin, activeRole), sparkData: _spark(filtered.map((m) => m.csPerMin).toList())),
      CalculatedMetric(label: 'DEATHS / GAME', value: avgDeaths.toStringAsFixed(1), status: checkStatus('deaths', avgDeaths, activeRole), sparkData: _spark(filtered.map((m) => m.deaths.toDouble()).toList())),
      CalculatedMetric(label: 'DEATH BY EARLY GANKS', value: avgEarlyGanks.toStringAsFixed(1), status: checkStatus('early_gank_deaths', avgEarlyGanks, activeRole), sparkData: _spark(filtered.map((m) => m.earlyGankDeaths.toDouble()).toList())),
    ]);
  } else if (activeRole == 'JUNGLE') {
    final avgGold14 = _avg(filtered.map((m) => m.goldDiff14).whereType<int>());
    final avgCs14 = _avg(filtered.map((m) => m.csDiff14).whereType<int>());
    final avgKda = _avg(filtered.map((m) => m.kdaValue));
    final avgCsMin = _avg(filtered.map((m) => m.csPerMin));
    final avgDeaths = _avg(filtered.map((m) => m.deaths));
    final avgEnemyJg = _avg(filtered.map((m) => m.enemyJgMonsters));
    final avgPinks = _avg(filtered.map((m) => m.controlWards));
    final setupRates = filtered.map((m) => m.dragonSetupRate).whereType<double>().toList();
    final avgDragonSetup = setupRates.isEmpty ? 0.0 : setupRates.reduce((a, b) => a + b) / setupRates.length;
    final drakeCount = filtered.where((m) => m.firstDragon).length;
    final heraldCount = filtered.where((m) => m.herald).length;
    final grubsCount = filtered.where((m) => m.voidGrubs).length;
    final objRate = ((drakeCount + heraldCount + grubsCount) / (3 * n)) * 100;

    metrics.addAll([
      CalculatedMetric(label: 'GOLD DIFF @14', value: '${avgGold14 >= 0 ? "+" : ""}${avgGold14.toStringAsFixed(0)}g', status: checkStatus('gold_diff_14', avgGold14, activeRole), sparkData: _spark(filtered.map((m) => (m.goldDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'CS DIFF @14', value: '${avgCs14 >= 0 ? "+" : ""}${avgCs14.toStringAsFixed(1)}', status: checkStatus('cs_diff_14', avgCs14, activeRole), sparkData: _spark(filtered.map((m) => (m.csDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'KDA', value: avgKda.toStringAsFixed(2), status: checkStatus('kda', avgKda, activeRole), sparkData: _spark(filtered.map((m) => m.kdaValue).toList())),
      CalculatedMetric(label: 'CS / MIN', value: avgCsMin.toStringAsFixed(1), status: checkStatus('cs_min', avgCsMin, activeRole), sparkData: _spark(filtered.map((m) => m.csPerMin).toList())),
      CalculatedMetric(label: 'DEATHS / GAME', value: avgDeaths.toStringAsFixed(1), status: checkStatus('deaths', avgDeaths, activeRole), sparkData: _spark(filtered.map((m) => m.deaths.toDouble()).toList())),
      CalculatedMetric(label: 'OBJECTIVES CONTROL', value: '${objRate.toStringAsFixed(1)}%', status: checkStatus('obj_control', objRate, activeRole), sparkData: _spark(filtered.map((m) => ((m.firstDragon ? 1 : 0) + (m.herald ? 1 : 0) + (m.voidGrubs ? 1 : 0)).toDouble() / 3 * 100).toList())),
      CalculatedMetric(label: 'DRAGON SETUP RATE', value: setupRates.isEmpty ? '—' : '${avgDragonSetup.toStringAsFixed(0)}%', status: checkStatus('dragon setup', avgDragonSetup, activeRole), sparkData: setupRates.isEmpty ? null : _spark(filtered.map((m) => m.dragonSetupRate ?? 0).toList())),
      CalculatedMetric(label: 'FIRST DRAGONS', value: '$drakeCount / $n', status: checkStatus('first_dragon', (drakeCount / n) * 100, activeRole)),
      CalculatedMetric(label: 'VOID GRUBS', value: '$grubsCount / $n', status: checkStatus('void_grubs', (grubsCount / n) * 100, activeRole)),
      CalculatedMetric(label: 'RIFT HERALDS', value: '$heraldCount / $n', status: checkStatus('rift_herald', (heraldCount / n) * 100, activeRole)),
      CalculatedMetric(label: 'OPPONENT CAMPS CLEARED', value: avgEnemyJg.toStringAsFixed(1), status: checkStatus('enemy_jg', avgEnemyJg, activeRole), sparkData: _spark(filtered.map((m) => m.enemyJgMonsters.toDouble()).toList())),
      CalculatedMetric(label: 'PINK WARDS / GAME', value: avgPinks.toStringAsFixed(1), status: checkStatus('pink_wards', avgPinks, activeRole), sparkData: _spark(filtered.map((m) => m.controlWards.toDouble()).toList())),
    ]);
  } else if (activeRole == 'MID') {
    final avgGold14 = _avg(filtered.map((m) => m.goldDiff14).whereType<int>());
    final avgCs14 = _avg(filtered.map((m) => m.csDiff14).whereType<int>());
    final avgKda = _avg(filtered.map((m) => m.kdaValue));
    final avgCsMin = _avg(filtered.map((m) => m.csPerMin));
    final avgDeaths = _avg(filtered.map((m) => m.deaths));
    final avgSoloDeaths = _avg(filtered.map((m) => m.deathEvents.where((d) => d.assistingParticipantIds.isEmpty).length));
    final avgRoams = _avg(filtered.map((m) => m.roamingProactivity));
    final avgEarlyGanks = _avg(filtered.map((m) => m.earlyGankDeaths));

    int laneDeaths = 0;
    int totalDeaths = 0;
    for (final m in filtered) {
      for (final d in m.deathEvents) {
        totalDeaths++;
        if (d.time < 840) laneDeaths++;
      }
    }
    final lanePct = totalDeaths > 0 ? (laneDeaths / totalDeaths) * 100 : 0.0;
    final sidePct = totalDeaths > 0 ? ((totalDeaths - laneDeaths) / totalDeaths) * 100 : 0.0;

    metrics.addAll([
      CalculatedMetric(label: 'GOLD DIFF @14', value: '${avgGold14 >= 0 ? "+" : ""}${avgGold14.toStringAsFixed(0)}g', status: checkStatus('gold_diff_14', avgGold14, activeRole), sparkData: _spark(filtered.map((m) => (m.goldDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'CS DIFF @14', value: '${avgCs14 >= 0 ? "+" : ""}${avgCs14.toStringAsFixed(1)}', status: checkStatus('cs_diff_14', avgCs14, activeRole), sparkData: _spark(filtered.map((m) => (m.csDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'KDA', value: avgKda.toStringAsFixed(2), status: checkStatus('kda', avgKda, activeRole), sparkData: _spark(filtered.map((m) => m.kdaValue).toList())),
      CalculatedMetric(label: 'CS / MIN', value: avgCsMin.toStringAsFixed(1), status: checkStatus('cs_min', avgCsMin, activeRole), sparkData: _spark(filtered.map((m) => m.csPerMin).toList())),
      CalculatedMetric(label: 'DEATHS / GAME', value: avgDeaths.toStringAsFixed(1), status: checkStatus('deaths', avgDeaths, activeRole), sparkData: _spark(filtered.map((m) => m.deaths.toDouble()).toList())),
      CalculatedMetric(label: 'SOLO DEATHS / GAME', value: avgSoloDeaths.toStringAsFixed(1), status: checkStatus('solo_deaths', avgSoloDeaths, activeRole), sparkData: _spark(filtered.map((m) => m.deathEvents.where((d) => d.assistingParticipantIds.isEmpty).length.toDouble()).toList())),
      CalculatedMetric(label: 'LANING DEATHS (PRE-14)', value: '${lanePct.toStringAsFixed(1)}%', status: checkStatus('lane_deaths', lanePct, activeRole), sparkData: _spark(filtered.map((m) => m.deathEvents.where((d) => d.time < 840).length.toDouble()).toList())),
      CalculatedMetric(label: 'SIDE DEATHS (POST-14)', value: '${sidePct.toStringAsFixed(1)}%', status: checkStatus('side_deaths', sidePct, activeRole), sparkData: _spark(filtered.map((m) => m.deathEvents.where((d) => d.time >= 840).length.toDouble()).toList())),
      CalculatedMetric(label: 'ROAMING PROACTIVITY', value: avgRoams.toStringAsFixed(1), status: checkStatus('roaming', avgRoams, activeRole), sparkData: _spark(filtered.map((m) => m.roamingProactivity.toDouble()).toList())),
      CalculatedMetric(label: 'DEATH BY EARLY GANKS', value: avgEarlyGanks.toStringAsFixed(1), status: checkStatus('early_gank_deaths', avgEarlyGanks, activeRole), sparkData: _spark(filtered.map((m) => m.earlyGankDeaths.toDouble()).toList())),
    ]);
  } else if (activeRole == 'ADC') {
    final avgGold14 = _avg(filtered.map((m) => m.goldDiff14).whereType<int>());
    final avgCs14 = _avg(filtered.map((m) => m.csDiff14).whereType<int>());
    final avgDmgShare = _avg(filtered.map((m) => m.damageShare));
    final avgGoldShare = _avg(filtered.map((m) => m.goldShare));
    final eff = avgGoldShare > 0 ? avgDmgShare / avgGoldShare : 0.0;
    final avgCsMin = _avg(filtered.map((m) => m.csPerMin));
    final avgKda = _avg(filtered.map((m) => m.kdaValue));
    final avgDeaths = _avg(filtered.map((m) => m.deaths));
    final avgEarlyGanks = _avg(filtered.map((m) => m.earlyGankDeaths));

    int laneDeaths = 0;
    int totalDeaths = 0;
    for (final m in filtered) {
      for (final d in m.deathEvents) {
        totalDeaths++;
        if (d.time < 840) laneDeaths++;
      }
    }
    final lanePct = totalDeaths > 0 ? (laneDeaths / totalDeaths) * 100 : 0.0;
    final sidePct = totalDeaths > 0 ? ((totalDeaths - laneDeaths) / totalDeaths) * 100 : 0.0;

    metrics.addAll([
      CalculatedMetric(label: 'GOLD DIFF @14', value: '${avgGold14 >= 0 ? "+" : ""}${avgGold14.toStringAsFixed(0)}g', status: checkStatus('gold_diff_14', avgGold14, activeRole), sparkData: _spark(filtered.map((m) => (m.goldDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'CS DIFF @14', value: '${avgCs14 >= 0 ? "+" : ""}${avgCs14.toStringAsFixed(1)}', status: checkStatus('cs_diff_14', avgCs14, activeRole), sparkData: _spark(filtered.map((m) => (m.csDiff14 ?? 0).toDouble()).toList())),
      CalculatedMetric(label: 'DAMAGE SHARE', value: '${avgDmgShare.toStringAsFixed(1)}%', status: checkStatus('dmg_share', avgDmgShare, activeRole), sparkData: _spark(filtered.map((m) => m.damageShare).toList())),
      CalculatedMetric(label: 'EFFICIENCY (DMG/GOLD)', value: eff.toStringAsFixed(2), status: checkStatus('efficiency', eff, activeRole), sparkData: _spark(filtered.map((m) => m.goldShare > 0 ? m.damageShare / m.goldShare : 0.0).toList())),
      CalculatedMetric(label: 'CS / MIN', value: avgCsMin.toStringAsFixed(1), status: checkStatus('cs_min', avgCsMin, activeRole), sparkData: _spark(filtered.map((m) => m.csPerMin).toList())),
      CalculatedMetric(label: 'LANING DEATHS (PRE-14)', value: '${lanePct.toStringAsFixed(1)}%', status: checkStatus('lane_deaths', lanePct, activeRole), sparkData: _spark(filtered.map((m) => m.deathEvents.where((d) => d.time < 840).length.toDouble()).toList())),
      CalculatedMetric(label: 'SIDE DEATHS (POST-14)', value: '${sidePct.toStringAsFixed(1)}%', status: checkStatus('side_deaths', sidePct, activeRole), sparkData: _spark(filtered.map((m) => m.deathEvents.where((d) => d.time >= 840).length.toDouble()).toList())),
      CalculatedMetric(label: 'KDA', value: avgKda.toStringAsFixed(2), status: checkStatus('kda', avgKda, activeRole), sparkData: _spark(filtered.map((m) => m.kdaValue).toList())),
      CalculatedMetric(label: 'DEATHS / GAME', value: avgDeaths.toStringAsFixed(1), status: checkStatus('deaths', avgDeaths, activeRole), sparkData: _spark(filtered.map((m) => m.deaths.toDouble()).toList())),
      CalculatedMetric(label: 'DEATH BY EARLY GANKS', value: avgEarlyGanks.toStringAsFixed(1), status: checkStatus('early_gank_deaths', avgEarlyGanks, activeRole), sparkData: _spark(filtered.map((m) => m.earlyGankDeaths.toDouble()).toList())),
    ]);
  } else {
    final avgVisionMin = _avg(filtered.map((m) => m.duration > 0 ? m.vision / (m.duration / 60) : 0.0));
    final avgPinks = _avg(filtered.map((m) => m.controlWards));
    final avgKp = _avg(filtered.map((m) => m.killParticipation));
    final avgVision = _avg(filtered.map((m) => m.vision));
    final avgDeaths = _avg(filtered.map((m) => m.deaths));
    final avgObjVision = _avg(filtered.map((m) => m.objectiveVisionScore));

    metrics.addAll([
      CalculatedMetric(label: 'VISION SCORE / MIN', value: avgVisionMin.toStringAsFixed(2), status: checkStatus('vision_min', avgVisionMin, activeRole), sparkData: _spark(filtered.map((m) => m.duration > 0 ? m.vision / (m.duration / 60) : 0.0).toList())),
      CalculatedMetric(label: 'PINK WARDS / GAME', value: avgPinks.toStringAsFixed(1), status: checkStatus('pink_wards', avgPinks, activeRole), sparkData: _spark(filtered.map((m) => m.controlWards.toDouble()).toList())),
      CalculatedMetric(label: 'KILL PARTICIPATION', value: '${avgKp.toStringAsFixed(1)}%', status: checkStatus('kp_percent', avgKp, activeRole), sparkData: _spark(filtered.map((m) => m.killParticipation).toList())),
      CalculatedMetric(label: 'VISION SCORE', value: avgVision.toStringAsFixed(1), status: checkStatus('vision_score', avgVision, activeRole), sparkData: _spark(filtered.map((m) => m.vision.toDouble()).toList())),
      CalculatedMetric(label: 'DEATHS / GAME', value: avgDeaths.toStringAsFixed(1), status: checkStatus('deaths', avgDeaths, activeRole), sparkData: _spark(filtered.map((m) => m.deaths.toDouble()).toList())),
      CalculatedMetric(label: 'OBJECTIVE PREP VISION SCORE', value: avgObjVision.toStringAsFixed(1), status: checkStatus('obj_vision', avgObjVision, activeRole), sparkData: _spark(filtered.map((m) => m.objectiveVisionScore.toDouble()).toList())),
    ]);
  }

  final avgDmgPerMin = _avg(filtered.map((m) => m.dmgPerMin));
  final avgGoldPerMin = _avg(filtered.map((m) => m.goldPerMin));
  metrics.addAll([
    CalculatedMetric(label: 'DMG / MIN', value: avgDmgPerMin.toStringAsFixed(0), status: checkStatus('dmg/min', avgDmgPerMin, activeRole), sparkData: _spark(filtered.map((m) => m.dmgPerMin).toList())),
    CalculatedMetric(label: 'GOLD / MIN', value: avgGoldPerMin.toStringAsFixed(0), status: checkStatus('gold/min', avgGoldPerMin, activeRole), sparkData: _spark(filtered.map((m) => m.goldPerMin).toList())),
  ]);

  return metrics;
}
