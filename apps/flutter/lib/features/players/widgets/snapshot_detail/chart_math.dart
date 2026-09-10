import 'package:fl_chart/fl_chart.dart';

List<FlSpot> regressionLine(List<FlSpot> spots) {
  if (spots.length < 2) return [];
  final n     = spots.length.toDouble();
  final sumX  = spots.fold(0.0, (s, p) => s + p.x);
  final sumY  = spots.fold(0.0, (s, p) => s + p.y);
  final sumXY = spots.fold(0.0, (s, p) => s + p.x * p.y);
  final sumX2 = spots.fold(0.0, (s, p) => s + p.x * p.x);
  final denom = n * sumX2 - sumX * sumX;
  if (denom == 0) return [];
  final slope     = (n * sumXY - sumX * sumY) / denom;
  final intercept = (sumY - slope * sumX) / n;
  return [
    FlSpot(spots.first.x, slope * spots.first.x + intercept),
    FlSpot(spots.last.x,  slope * spots.last.x  + intercept),
  ];
}
