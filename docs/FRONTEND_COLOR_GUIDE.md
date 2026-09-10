# Guía de Integración de Umbrales y Colores en YGG (Estilo OP.GG)

Esta guía está diseñada para que el desarrollador encargado del Frontend (Flutter) pueda unificar y sincronizar los colores visuales de las estadísticas con el sistema semántico centralizado en el Backend, utilizando el estilo de clasificación de **OP.GG**.

---

## 1. Paleta de Colores de Estadísticas (Tema de YGG)

Los colores semánticos que representan la calidad de una métrica se encuentran definidos en el archivo de configuración de estilos global del frontend:

**Archivo:** `frontend/lib/core/theme/app_theme.dart`

```dart
// Colores de estadísticas (estilo OP.GG)
const Color kStatGold   = Color(0xFFFF9F19); // Excelente (KDA >= 5.0) -> Dorado / Naranja Hextech
const Color kStatBlue   = Color(0xFF38BDF8); // Bueno (KDA >= 4.0) -> Azul Hextech
const Color kStatGreen  = Color(0xFF4ADE80); // Normal (KDA >= 3.0) -> Verde Hextech
const Color kStatGray   = Color(0xFF94A3B8); // Malo (KDA < 3.0) -> Gris Neutro / Apagado
const Color kStatRed    = Color(0xFFF87171); // Stats Negativas (Altas muertes) -> Rojo de alerta
```

---

## 2. Consumo de la Evaluación Semántica del Backend

El backend centraliza la evaluación de todas las métricas promedio del Dashboard del Jugador y de los Snapshots a través del campo **`status`** de cada objeto `RoleAverageMetric`. 

El campo `status` retorna uno de estos cuatro valores en texto:
1. `"excellent"`
2. `"good"`
3. `"normal"`
4. `"bad"`

### Función de utilidad recomendada para el Frontend
Para realizar el mapeo de colores estilo **OP.GG** de forma limpia y consistente (donde las estadísticas normales son verdes, las excelentes doradas, las malas grises y solo las **muertes/stats negativas** críticas se pintan de **rojo**), se recomienda el siguiente helper en Flutter:

```dart
Color getStatColor(String metricKey, String status) {
  final key = metricKey.toLowerCase();
  final s = status.toLowerCase();

  // Detectar si es una métrica de carácter negativo (Muertes)
  final isNegativeStat = key.contains('deaths') || key.contains('death') || key.contains('muertes');

  if (isNegativeStat) {
    switch (s) {
      case 'bad':
        return kStatRed;      // Demasiadas muertes -> Rojo de Alerta
      case 'normal':
        return kStatGray;     // Muertes promedio -> Gris neutro
      case 'good':
        return kStatBlue;     // Pocas muertes -> Azul bueno
      case 'excellent':
        return kStatGold;     // Casi ninguna muerte -> Dorado excelente
      default:
        return kStatGray;
    }
  }

  // Métricas estándar o positivas (KDA, CS/Min, Objetivos, etc.)
  switch (s) {
    case 'excellent':
      return kStatGold;   // Excelente (KDA >= 5.0, etc.) -> Dorado / Naranja
    case 'good':
      return kStatBlue;   // Bueno (KDA >= 4.0, etc.) -> Azul
    case 'normal':
      return kStatGreen;  // Normal (KDA >= 3.0, etc.) -> Verde
    case 'bad':
    default:
      return kStatGray;   // Malo (KDA < 3.0, etc.) -> Gris
  }
}
```

Al utilizar este helper, cualquier cambio futuro en los umbrales de las estadísticas en el backend se reflejará **automáticamente** en la UI con la lógica de colores correcta.

---

## 3. Ajuste de Widgets Clave en el Frontend

Para asegurar la consistencia total en las lógicas locales del Frontend:

### A. Panel de Campeones Más Jugados
**Archivo:** `frontend/lib/features/players/widgets/champion_stats_panel.dart`

* **Función actual:** `_wrColor(double wr)`
* **Refactorización recomendada (Mapeo de Winrate):**
  * **Winrate $\ge 55\%$**: `kStatGold` (Excelente / Dorado)
  * **Winrate $\ge 50\%$**: `kStatBlue` (Bueno / Azul)
  * **Winrate $\ge 45\%$**: `kStatGreen` (Normal / Verde)
  * **Winrate $< 45\%$**: `kStatGray` (Malo o mediocre / Gris)

```dart
Color _wrColor(double wr) {
  if (wr >= 55.0) return kStatGold;
  if (wr >= 50.0) return kStatBlue;
  if (wr >= 45.0) return kStatGreen;
  return kStatGray;
}
```

---

### B. Historial de Partidas Recientes (KDA)
**Archivo:** `frontend/lib/features/players/widgets/match_history_panel.dart`

* **Función actual:** `_kdaColor(double kda)`
* **Refactorización recomendada (Mapeo de KDA estilo OP.GG):**
  * **KDA $\ge 5.0$**: `kStatGold` (Dorado)
  * **KDA $\ge 4.0$**: `kStatBlue` (Azul)
  * **KDA $\ge 3.0$**: `kStatGreen` (Verde)
  * **KDA $< 3.0$**: `kStatGray` (Gris)

```dart
Color _kdaColor(double kda) {
  if (kda >= 5.0) return kStatGold;
  if (kda >= 4.0) return kStatBlue;
  if (kda >= 3.0) return kStatGreen;
  return kStatGray;
}
```

---

### C. Fila de la Tabla General de Jugadores
**Archivo:** `frontend/lib/features/players/widgets/player_row.dart`

* **Lógica actual:** Pinta el winrate en verde si es $\ge 55\%$.
* **Refactorización recomendada:**
  Utilizar la misma escala de winrates uniforme de la aplicación para mayor armonía:

```dart
Color getWinRateColor(double winRate) {
  if (winRate >= 55.0) return kStatGold;
  if (winRate >= 50.0) return kStatBlue;
  if (winRate >= 45.0) return kStatGreen;
  return kStatGray;
}
```

---

## 4. Tabla de Criterios Semánticos en el Backend (Referencia)

| Métrica | Excelente (`excellent` $\rightarrow$ Dorado) | Bueno (`good` $\rightarrow$ Azul) | Normal (`normal` $\rightarrow$ Verde) | Malo (`bad` $\rightarrow$ Gris / Rojo) |
| :--- | :--- | :--- | :--- | :--- |
| **KDA** | $\ge 5.0$ | $\ge 4.0$ | $\ge 3.0$ | $< 3.0$ (Gris) |
| **CS/Min** | $\ge 10.0$ | $\ge 9.0$ | $\ge 8.0$ | $< 8.0$ (Gris) |
| **Muertes (Métrica Negativa)** | $\le 3.0$ (Dorado) | $\le 4.0$ (Azul) | $\le 5.0$ (Gris) | $> 5.0$ (**Rojo**) |
| **Solo Kills** | $\ge 2.0$ | $\ge 1.0$ | $\ge 0.5$ | $< 0.5$ (Gris) |
| **Solo Deaths (Negativa)** | $\le 0.4$ (Dorado) | $\le 0.8$ (Azul) | $\le 1.2$ (Gris) | $> 1.2$ (**Rojo**) |
| **Gold Diff @14** | $\ge +500\text{g}$ | $\ge +200\text{g}$ | $\ge -100\text{g}$ | $< -100\text{g}$ (Gris) |
| **CS Diff @14** | $\ge +15\text{ cs}$ | $\ge +8\text{ cs}$ | $\ge 0\text{ cs}$ | $< 0\text{ cs}$ (Gris) |
| **Pinks (Soporte)** | $\ge 8$ | $\ge 6$ | $\ge 4$ | $< 4$ (Gris) |
| **Pinks (Jungla)** | $\ge 6$ | $\ge 4$ | $\ge 2$ | $< 2$ (Gris) |
| **Pinks (Otros)** | $\ge 4$ | $\ge 2.5$ | $\ge 1.5$ | $< 1.5$ (Gris) |
| **Eficiencia Oro/Daño** | $\ge 1.2$ | $\ge 1.0$ | $\ge 0.8$ | $< 0.8$ (Gris) |
| **Control Objetivos** | $\ge 60\%$ | $\ge 50\%$ | $\ge 40\%$ | $< 40\%$ (Gris) |
| **Daño Estructuras** | $\ge 8000$ | $\ge 6000$ | $\ge 4000$ | $< 4000$ (Gris) |
| **Campamentos Robados** | $\ge 15$ | `\ge 10` | $\ge 6$ | $< 6$ (Gris) |
| **Prep. de Visión** | $\ge 6.0$ | $\ge 4.0$ | $\ge 2.5$ | $< 2.5$ (Gris) |
| **Roaming** | $\ge 4.0$ | $\ge 2.5$ | $\ge 1.5$ | $< 1.5$ (Gris) |
| **Muertes Pre-14 (Negativa)**| $\le 30\%$ (Dorado) | $\le 45\%$ (Azul) | $\le 60\%$ (Gris) | $> 60\%$ (**Rojo**) |
| **Muertes Post-14 (Negativa)**| $\le 20\%$ (Dorado) | $\le 35\%$ (Azul) | $\le 50\%$ (Gris) | $> 50\%$ (**Rojo**) |
