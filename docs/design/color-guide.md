# Guide to integrating thresholds and colours in YGG (OP.GG style)

> **Note.** Written for the TFG's Flutter client. The current (React) client applies the same thresholds and colours in
> `apps/web/src/lib/stats.ts`, and each metric's status is computed by the backend in
> `packages/ygg-core/src/ygg_core/metrics/status.py`.

This guide is designed so that the developer in charge of the frontend (Flutter) can unify and synchronise the statistics'
visual colours with the semantic system centralised in the backend, using **OP.GG**'s classification style.

---

## 1. Statistics colour palette (YGG theme)

The semantic colours that represent a metric's quality are defined in the frontend's global style configuration file:

**File:** `frontend/lib/core/theme/app_theme.dart`

```dart
// Statistics colours (OP.GG style)
const Color kStatGold   = Color(0xFFFF9F19); // Excellent (KDA >= 5.0) -> Hextech gold / orange
const Color kStatBlue   = Color(0xFF38BDF8); // Good (KDA >= 4.0) -> Hextech blue
const Color kStatGreen  = Color(0xFF4ADE80); // Normal (KDA >= 3.0) -> Hextech green
const Color kStatGray   = Color(0xFF94A3B8); // Bad (KDA < 3.0) -> neutral / muted grey
const Color kStatRed    = Color(0xFFF87171); // Negative stats (high deaths) -> alert red
```

---

## 2. Consuming the backend's semantic evaluation

The backend centralises the evaluation of all the average metrics of the Player Dashboard and of the Snapshots through the
**`status`** field of each `RoleAverageMetric` object.

The `status` field returns one of these four text values:
1. `"excellent"`
2. `"good"`
3. `"normal"`
4. `"bad"`

### Recommended utility function for the frontend
To do the **OP.GG**-style colour mapping cleanly and consistently (where normal stats are green, excellent ones gold, bad
ones grey and only critical **deaths / negative stats** are painted **red**), the following helper in Flutter is
recommended:

```dart
Color getStatColor(String metricKey, String status) {
  final key = metricKey.toLowerCase();
  final s = status.toLowerCase();

  // Detect whether it is a negative-natured metric (Deaths)
  final isNegativeStat = key.contains('deaths') || key.contains('death');

  if (isNegativeStat) {
    switch (s) {
      case 'bad':
        return kStatRed;      // Too many deaths -> alert red
      case 'normal':
        return kStatGray;     // Average deaths -> neutral grey
      case 'good':
        return kStatBlue;     // Few deaths -> good blue
      case 'excellent':
        return kStatGold;     // Almost no deaths -> excellent gold
      default:
        return kStatGray;
    }
  }

  // Standard or positive metrics (KDA, CS/Min, Objectives, etc.)
  switch (s) {
    case 'excellent':
      return kStatGold;   // Excellent (KDA >= 5.0, etc.) -> gold / orange
    case 'good':
      return kStatBlue;   // Good (KDA >= 4.0, etc.) -> blue
    case 'normal':
      return kStatGreen;  // Normal (KDA >= 3.0, etc.) -> green
    case 'bad':
    default:
      return kStatGray;   // Bad (KDA < 3.0, etc.) -> grey
  }
}
```

By using this helper, any future change to the statistics' thresholds in the backend will be reflected **automatically** in
the UI with the right colour logic.

---

## 3. Adjusting key widgets in the frontend

To ensure complete consistency in the frontend's local logic:

### A. Most-played champions panel
**File:** `frontend/lib/features/players/widgets/champion_stats_panel.dart`

* **Current function:** `_wrColor(double wr)`
* **Recommended refactor (winrate mapping):**
  * **Winrate $\ge 55\%$**: `kStatGold` (Excellent / gold)
  * **Winrate $\ge 50\%$**: `kStatBlue` (Good / blue)
  * **Winrate $\ge 45\%$**: `kStatGreen` (Normal / green)
  * **Winrate $< 45\%$**: `kStatGray` (Bad or mediocre / grey)

```dart
Color _wrColor(double wr) {
  if (wr >= 55.0) return kStatGold;
  if (wr >= 50.0) return kStatBlue;
  if (wr >= 45.0) return kStatGreen;
  return kStatGray;
}
```

---

### B. Recent games history (KDA)
**File:** `frontend/lib/features/players/widgets/match_history_panel.dart`

* **Current function:** `_kdaColor(double kda)`
* **Recommended refactor (OP.GG-style KDA mapping):**
  * **KDA $\ge 5.0$**: `kStatGold` (gold)
  * **KDA $\ge 4.0$**: `kStatBlue` (blue)
  * **KDA $\ge 3.0$**: `kStatGreen` (green)
  * **KDA $< 3.0$**: `kStatGray` (grey)

```dart
Color _kdaColor(double kda) {
  if (kda >= 5.0) return kStatGold;
  if (kda >= 4.0) return kStatBlue;
  if (kda >= 3.0) return kStatGreen;
  return kStatGray;
}
```

---

### C. Row of the general players table
**File:** `frontend/lib/features/players/widgets/player_row.dart`

* **Current logic:** it paints the winrate green if it is $\ge 55\%$.
* **Recommended refactor:**
  Use the application's same uniform winrate scale for greater harmony:

```dart
Color getWinRateColor(double winRate) {
  if (winRate >= 55.0) return kStatGold;
  if (winRate >= 50.0) return kStatBlue;
  if (winRate >= 45.0) return kStatGreen;
  return kStatGray;
}
```

---

## 4. Table of semantic criteria in the backend (reference)

| Metric | Excellent (`excellent` $\rightarrow$ Gold) | Good (`good` $\rightarrow$ Blue) | Normal (`normal` $\rightarrow$ Green) | Bad (`bad` $\rightarrow$ Grey / Red) |
| :--- | :--- | :--- | :--- | :--- |
| **KDA** | $\ge 5.0$ | $\ge 4.0$ | $\ge 3.0$ | $< 3.0$ (Grey) |
| **CS/Min** | $\ge 10.0$ | $\ge 9.0$ | $\ge 8.0$ | $< 8.0$ (Grey) |
| **Deaths (negative metric)** | $\le 3.0$ (Gold) | $\le 4.0$ (Blue) | $\le 5.0$ (Grey) | $> 5.0$ (**Red**) |
| **Solo kills** | $\ge 2.0$ | $\ge 1.0$ | $\ge 0.5$ | $< 0.5$ (Grey) |
| **Solo deaths (negative)** | $\le 0.4$ (Gold) | $\le 0.8$ (Blue) | $\le 1.2$ (Grey) | $> 1.2$ (**Red**) |
| **Gold Diff @14** | $\ge +500\text{g}$ | $\ge +200\text{g}$ | $\ge -100\text{g}$ | $< -100\text{g}$ (Grey) |
| **CS Diff @14** | $\ge +15\text{ cs}$ | $\ge +8\text{ cs}$ | $\ge 0\text{ cs}$ | $< 0\text{ cs}$ (Grey) |
| **Pinks (Support)** | $\ge 8$ | $\ge 6$ | $\ge 4$ | $< 4$ (Grey) |
| **Pinks (Jungle)** | $\ge 6$ | $\ge 4$ | $\ge 2$ | $< 2$ (Grey) |
| **Pinks (Others)** | $\ge 4$ | $\ge 2.5$ | $\ge 1.5$ | $< 1.5$ (Grey) |
| **Gold/Damage efficiency** | $\ge 1.2$ | $\ge 1.0$ | $\ge 0.8$ | $< 0.8$ (Grey) |
| **Objective control** | $\ge 60\%$ | $\ge 50\%$ | $\ge 40\%$ | $< 40\%$ (Grey) |
| **Structure damage** | $\ge 8000$ | $\ge 6000$ | $\ge 4000$ | $< 4000$ (Grey) |
| **Stolen camps** | $\ge 15$ | `\ge 10` | $\ge 6$ | $< 6$ (Grey) |
| **Vision prep.** | $\ge 6.0$ | $\ge 4.0$ | $\ge 2.5$ | $< 2.5$ (Grey) |
| **Roaming** | $\ge 4.0$ | $\ge 2.5$ | $\ge 1.5$ | $< 1.5$ (Grey) |
| **Pre-14 deaths (negative)**| $\le 30\%$ (Gold) | $\le 45\%$ (Blue) | $\le 60\%$ (Grey) | $> 60\%$ (**Red**) |
| **Post-14 deaths (negative)**| $\le 20\%$ (Gold) | $\le 35\%$ (Blue) | $\le 50\%$ (Grey) | $> 50\%$ (**Red**) |
