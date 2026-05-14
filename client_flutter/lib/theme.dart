import 'package:flutter/material.dart';

/// Colors used across the app. Centralised so retheming is one place.
class AppColors {
  // table
  static const tableFelt = Color(0xFF1A4F3A);
  static const tableFeltDeep = Color(0xFF0E2A20);
  static const tableEdge = Color(0xFF3D2817);

  // accents
  static const gold = Color(0xFFD4A857);
  static const goldBright = Color(0xFFF0C97D);
  static const goldDim = Color(0xFF8A6E3F);

  // semantic colors
  static const ron = Color(0xFFE54B4B);
  static const tsumo = Color(0xFFFFA94D);
  static const riichi = Color(0xFFFFCB69);
  static const danger = Color(0xFFE54B4B);

  // surfaces
  static const surface = Color(0xFF1D1410);
  static const surfaceRaised = Color(0xFF291B14);

  // text
  static const textPrimary = Color(0xFFF5E9D3);
  static const textSecondary = Color(0xFFC4B59E);
  static const textDim = Color(0xFF8A7C65);
}

ThemeData buildTheme() {
  const base = ColorScheme.dark(
    primary: AppColors.gold,
    onPrimary: AppColors.surface,
    secondary: AppColors.goldBright,
    onSecondary: AppColors.surface,
    surface: AppColors.surface,
    onSurface: AppColors.textPrimary,
    error: AppColors.danger,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: base,
    scaffoldBackgroundColor: AppColors.tableFelt,
    fontFamily: 'serif',
    textTheme: const TextTheme(
      headlineLarge: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w700),
      titleMedium: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600),
      bodyMedium: TextStyle(color: AppColors.textPrimary),
      labelMedium: TextStyle(color: AppColors.textSecondary, letterSpacing: 0.5),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.gold,
        foregroundColor: AppColors.surface,
        textStyle: const TextStyle(fontWeight: FontWeight.w700, letterSpacing: 1.2),
        shape: const StadiumBorder(),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 12),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        side: const BorderSide(color: AppColors.gold, width: 1.4),
        foregroundColor: AppColors.goldBright,
        shape: const StadiumBorder(),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
      ),
    ),
    inputDecorationTheme: const InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surfaceRaised,
      hintStyle: TextStyle(color: AppColors.textDim),
      labelStyle: TextStyle(color: AppColors.textSecondary),
      border: OutlineInputBorder(
        borderSide: BorderSide(color: AppColors.goldDim),
        borderRadius: BorderRadius.all(Radius.circular(8)),
      ),
      enabledBorder: OutlineInputBorder(
        borderSide: BorderSide(color: AppColors.goldDim),
        borderRadius: BorderRadius.all(Radius.circular(8)),
      ),
      focusedBorder: OutlineInputBorder(
        borderSide: BorderSide(color: AppColors.gold, width: 1.6),
        borderRadius: BorderRadius.all(Radius.circular(8)),
      ),
    ),
  );
}
