import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';

const _fallbackVersion = '16.10.1';

/// Elimina etiquetas HTML del texto devuelto por Data Dragon.
String stripHtml(String html) {
  return html
      .replaceAll(RegExp(r'<br\s*/?>', caseSensitive: false), '\n')
      .replaceAll(RegExp(r'<[^>]+>'), '')
      .replaceAll(RegExp(r'\n{3,}'), '\n\n')
      .trim();
}

final ddragonVersionProvider = FutureProvider<String>((ref) async {
  try {
    final res = await ApiClient.instance.dio.get(Endpoints.ddragonVersion);
    return res.data as String? ?? _fallbackVersion;
  } catch (_) {
    return _fallbackVersion;
  }
});

final ddragonMapUrlProvider = FutureProvider<String>((ref) async {
  try {
    final res = await ApiClient.instance.dio.get(Endpoints.ddragonMapUrl);
    final url = (res.data as Map<String, dynamic>)['url'] as String?;
    if (url != null && url.isNotEmpty) return url;
  } catch (_) {}

  try {
    final version = await ref.watch(ddragonVersionProvider.future);
    return 'https://ddragon.leagueoflegends.com/cdn/$version/img/map/map11.png';
  } catch (_) {
    return 'https://ddragon.leagueoflegends.com/cdn/$_fallbackVersion/img/map/map11.png';
  }
});

// Mapea item ID → (nombre, descripción limpia, coste total)
final itemDataProvider = FutureProvider<Map<int, ({String name, String desc, int cost})>>((ref) async {
  try {
    final res  = await ApiClient.instance.dio.get(Endpoints.ddragonItems);
    final data = res.data as Map<String, dynamic>;
    return {
      for (final entry in data.entries)
        if (int.tryParse(entry.key) != null)
          int.parse(entry.key): (
            name: entry.value['name'] as String? ?? '',
            desc: stripHtml(entry.value['description'] as String? ?? ''),
            cost: (entry.value['gold']?['total'] as num?)?.toInt() ?? 0,
          ),
    };
  } catch (_) {
    return {};
  }
});

// Mapea summoner spell ID numérico → (nombre, descripción limpia, cooldown)
final spellDataProvider = FutureProvider<Map<int, ({String name, String desc, int cooldown})>>((ref) async {
  try {
    final res  = await ApiClient.instance.dio.get(Endpoints.ddragonSpells);
    final data = res.data as Map<String, dynamic>;
    return {
      for (final spell in data.values)
        if (int.tryParse(spell['key'] as String? ?? '') != null)
          int.parse(spell['key']): (
            name:     spell['name'] as String? ?? '',
            desc:     stripHtml(spell['description'] as String? ?? ''),
            cooldown: ((spell['cooldown'] as List?)?.firstOrNull as num?)?.toInt() ?? 0,
          ),
    };
  } catch (_) {
    return {};
  }
});

// Mapea keystone rune ID y tree ID → (nombre, descripción, URL del icono)
final runeIconsProvider = FutureProvider<Map<int, ({String name, String icon, String desc})>>((ref) async {
  try {
    final res   = await ApiClient.instance.dio.get(Endpoints.ddragonRunes);
    final trees = res.data as List<dynamic>;
    final map   = <int, ({String name, String icon, String desc})>{};
    for (final tree in trees) {
      // Árbol secundario (top-level) — sin descripción propia
      final treeId   = tree['id']   as int?;
      final treeName = tree['name'] as String? ?? '';
      final treeIcon = tree['icon'] as String? ?? '';
      if (treeId != null && treeIcon.isNotEmpty) {
        map[treeId] = (
          name: treeName,
          icon: 'https://ddragon.leagueoflegends.com/cdn/img/$treeIcon',
          desc: '',
        );
      }
      // Runas individuales (keystones y menores)
      for (final slot in (tree['slots'] as List? ?? [])) {
        for (final rune in (slot['runes'] as List? ?? [])) {
          final id   = rune['id']   as int?;
          final name = rune['name'] as String? ?? '';
          final icon = rune['icon'] as String? ?? '';
          final desc = stripHtml(rune['shortDesc'] as String? ?? '');
          if (id != null && icon.isNotEmpty) {
            map[id] = (
              name: name,
              icon: 'https://ddragon.leagueoflegends.com/cdn/img/$icon',
              desc: desc,
            );
          }
        }
      }
    }
    return map;
  } catch (_) {
    return {};
  }
});

// Mapea summoner spell ID numérico → URL del icono en ddragon
// Ej: 4 → "https://ddragon.../spell/SummonerFlash.png"
final spellIconsProvider = FutureProvider<Map<int, String>>((ref) async {
  try {
    final version = await ref.watch(ddragonVersionProvider.future);
    final res     = await ApiClient.instance.dio.get(Endpoints.ddragonSpells);
    final data    = res.data as Map<String, dynamic>;
    final map     = <int, String>{};
    for (final spell in data.values) {
      final key     = int.tryParse(spell['key'] as String? ?? '');
      final spellId = spell['id']  as String?;
      if (key != null && spellId != null) {
        map[key] = 'https://ddragon.leagueoflegends.com/cdn/$version/img/spell/$spellId.png';
      }
    }
    return map;
  } catch (_) {
    return {};
  }
});
