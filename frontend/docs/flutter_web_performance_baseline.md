# Flutter Web Performance Baseline

This document defines a repeatable baseline for UI performance checks in web.

## 1) Build mode

Do not evaluate performance in debug mode.

- Profile run:
  - `flutter run -d chrome --profile`
- Release run:
  - `flutter run -d chrome --release`

## 2) Scenario to measure

Use always the same flow:

1. Open one snapshot with many games.
2. Navigate to the stats/charts section.
3. Wait until all charts are visible.
4. Scroll down and up two full passes.
5. Toggle chart controls (metric chips, challenger line, etc.).

## 3) DevTools metrics

Open Flutter DevTools and record:

- Average frame build time (ms).
- Average raster time (ms).
- Janky frames count (frames above 16 ms).
- Time to first meaningful paint of charts section.

## 4) Acceptance targets

- Build and raster mostly under 16 ms.
- Visible reduction of janky spikes during chart interactions.
- Faster first paint of charts section versus baseline.

## 5) Log template

Use this template per run:

- Date:
- Commit/branch:
- Mode (profile/release):
- Snapshot id:
- Build avg (ms):
- Raster avg (ms):
- Janky frames:
- First charts paint (s):
- Notes:
