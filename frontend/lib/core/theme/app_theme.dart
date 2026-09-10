import 'package:flutter/material.dart';

// ── Paleta de colores Hextech ──────────────────────────────────────────────────
// Traducción directa de los valores HSL del prototipo React a Color de Flutter.

const Color kBgColor      = Color(0xFF110F1A); // hsl(252 28% 8%)  — fondo principal
const Color kSurfaceColor = Color(0xFF181523); // hsl(252 25% 11%) — tarjetas/paneles
const Color kSurface2     = Color(0xFF1D1A2C); // hsl(252 25% 14%) — filas hover
const Color kPrimary      = Color(0xFF9E5AE2); // hsl(270 70% 62%) — púrpura principal
const Color kPrimaryLight = Color(0xFFC79AF4); // hsl(270 80% 78%) — títulos/etiquetas
const Color kPrimaryDim   = Color(0xFF6B3A9E); // hsl(270 50% 42%) — variante oscura
const Color kBorderColor  = Color(0xFF2A2040); // hsl(270 30% 19%) — bordes sutiles
const Color kMuted        = Color(0xFF6B6578); // muted-foreground
const Color kForeground   = Color(0xFFE8E0F5); // texto principal

const Color kStatGold   = Color(0xFFFF9F19); // Excelente KDA >= 5 / Dorado
const Color kStatBlue   = Color(0xFF38BDF8); // Bueno KDA >= 4 / Azul
const Color kStatGreen  = Color(0xFF4ADE80); // Normal KDA >= 3 / Verde
const Color kStatGray   = Color(0xFF94A3B8); // Malo KDA < 3 / Gris (antes kMuted)
const Color kStatRed    = Color(0xFFF87171); // Estadísticas negativas / Muertes / Rojo

class AppTheme {
  AppTheme._();

  static ThemeData get dark => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    fontFamily: 'DMSans',
    scaffoldBackgroundColor: kBgColor,
    colorScheme: const ColorScheme.dark(
      surface:          kSurfaceColor,
      primary:          kPrimary,
      onPrimary:        Colors.white,
      onSurface:        kForeground,
      secondary:        kPrimaryDim,
      onSecondary:      Colors.white,
      outline:          kBorderColor,
      surfaceContainer: kSurface2,
    ),
    textTheme: const TextTheme(
      displayLarge:  TextStyle(color: kPrimaryLight, fontWeight: FontWeight.bold, letterSpacing: 3.0),
      titleLarge:    TextStyle(color: kPrimaryLight, fontWeight: FontWeight.bold, letterSpacing: 2.0),
      titleMedium:   TextStyle(color: kForeground,   fontWeight: FontWeight.w600),
      bodyMedium:    TextStyle(color: kForeground),
      bodySmall:     TextStyle(color: kMuted,         fontSize: 12),
      labelSmall:    TextStyle(color: kMuted,         fontSize: 10, letterSpacing: 1.5),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: kSurface2,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: kBorderColor),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: kBorderColor.withValues(alpha: 0.6)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: kPrimary, width: 1.5),
      ),
      hintStyle: const TextStyle(color: kMuted, fontSize: 13),
      labelStyle: const TextStyle(color: kMuted, fontSize: 11, letterSpacing: 1.2),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: kPrimary,
        foregroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: const TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1.5),
      ).copyWith(
        mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: kPrimaryLight,
        side: const BorderSide(color: kPrimary),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ).copyWith(
        mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom().copyWith(
        mouseCursor: WidgetStateProperty.all(SystemMouseCursors.click),
      ),
    ),
    dividerTheme: const DividerThemeData(color: kBorderColor, thickness: 1),
    cardTheme: CardThemeData(
      color: kSurfaceColor,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: kBorderColor),
      ),
    ),
    dropdownMenuTheme: DropdownMenuThemeData(
      menuStyle: MenuStyle(
        backgroundColor: WidgetStatePropertyAll(kSurface2),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: const BorderSide(color: kBorderColor),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: kSurface2,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: kBorderColor),
        ),
      ),
    ),
  );
}
