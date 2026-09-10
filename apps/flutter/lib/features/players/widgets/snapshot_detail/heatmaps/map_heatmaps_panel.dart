import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../../core/theme/app_theme.dart';
import '../../../models/match_model.dart';
import '../../../providers/match_provider.dart';
import '../chart_shared_widgets.dart';
import 'heatmap_math.dart';
import 'map_heatmap_card.dart';

enum _MapHeatmapTab { deaths, vision }

class MapHeatmapsPanel extends ConsumerStatefulWidget {
  const MapHeatmapsPanel({
    super.key,
    required this.snapshotId,
    required this.activeRole,
    this.champion,
  });

  final int snapshotId;
  final String activeRole;
  final String? champion;

  @override
  ConsumerState<MapHeatmapsPanel> createState() => _MapHeatmapsPanelState();
}

class _MapHeatmapsPanelState extends ConsumerState<MapHeatmapsPanel> {
  late _MapHeatmapTab _tab;

  @override
  void initState() {
    super.initState();
    _tab = _MapHeatmapTab.deaths;
  }

  List<_MapHeatmapTab> get _availableTabs {
    final tabs = <_MapHeatmapTab>[_MapHeatmapTab.deaths];
    if (widget.activeRole == 'SUPPORT') {
      tabs.add(_MapHeatmapTab.vision);
    }
    return tabs;
  }

  @override
  void didUpdateWidget(covariant MapHeatmapsPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_availableTabs.contains(_tab)) {
      _tab = _availableTabs.first;
    }
  }

  List<MatchModel> _filterMatches(List<MatchModel> all) {
    if (widget.champion != null) {
      return all.where((m) => m.champion == widget.champion).toList();
    }
    return all;
  }

  @override
  Widget build(BuildContext context) {
    final matchesAsync = ref.watch(snapshotMatchesProvider(widget.snapshotId));

    return matchesAsync.when(
      loading: () => const ChartCard(
        title: 'Map Heatmaps',
        subtitle: 'Loading spatial data...',
        child: SizedBox(
          height: 120,
          child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: kPrimary)),
        ),
      ),
      error: (error, stackTrace) => const ChartCard(
        title: 'Map Heatmaps',
        subtitle: 'Could not load match data',
        child: SizedBox(height: 80),
      ),
      data: (allMatches) {
        final matches = _filterMatches(allMatches);
        final tabs = _availableTabs;
        if (!tabs.contains(_tab)) _tab = tabs.first;

        final config = _configForTab(_tab);
        final points = _pointsForTab(_tab, matches);

        final narrow = MediaQuery.of(context).size.width < 600;
        return ChartCard(
          title: 'Map Heatmaps',
          subtitle: 'Brighter zones = more activity · Filtered by champion selection',
          onFullscreen: narrow && !chartIsInFullscreen(context)
              ? () => FullscreenChartScreen.push(
                    context,
                    MapHeatmapsPanel(
                      snapshotId: widget.snapshotId,
                      activeRole: widget.activeRole,
                      champion:   widget.champion,
                    ),
                  )
              : null,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (tabs.length > 1)
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 8,
                  runSpacing: 8,
                  children: tabs.map((t) {
                    return MetricChip(
                      label: _tabLabel(t),
                      selected: _tab == t,
                      onTap: () => setState(() => _tab = t),
                    );
                  }).toList(),
                ),
              if (tabs.length > 1) const SizedBox(height: 14),
              CompactHeatmapView(
                points: points,
                accentColor: config.color,
                gameCount: matches.length,
                label: config.label,
                hint: config.hint,
              ),
            ],
          ),
        );
      },
    );
  }

  String _tabLabel(_MapHeatmapTab tab) {
    switch (tab) {
      case _MapHeatmapTab.deaths:
        return 'DEATHS';
      case _MapHeatmapTab.vision:
        return 'VISION';
    }
  }

  List<HeatmapPoint> _pointsForTab(_MapHeatmapTab tab, List<MatchModel> matches) {
    switch (tab) {
      case _MapHeatmapTab.deaths:
        return matches
            .expand((m) => m.deathEvents)
            .map((d) => HeatmapPoint(d.normX, d.normY))
            .toList();
      case _MapHeatmapTab.vision:
        return matches
            .expand((m) => m.wardEvents)
            .map((w) => HeatmapPoint(w.normX, w.normY))
            .toList();
    }
  }

  ({Color color, String label, String hint}) _configForTab(_MapHeatmapTab tab) {
    switch (tab) {
      case _MapHeatmapTab.deaths:
        return (
          color: const Color(0xFFFF5555),
          label: 'Death locations',
          hint: 'Where you died most often across filtered games.',
        );
      case _MapHeatmapTab.vision:
        return (
          color: const Color(0xFF5EB8FF),
          label: 'Ward placements',
          hint: 'Where you placed wards most often.',
        );
    }
  }
}
