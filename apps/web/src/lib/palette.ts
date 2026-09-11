/**
 * Colores en hex para los gráficos SVG: los atributos de presentación (stroke,
 * fill) no aceptan var(). Es un espejo de los tokens de styles/index.css.
 *
 * `primary` es el acento de interfaz (verde ácido) y representa al jugador en las
 * gráficas; el resto de colores de datos mantienen su significado.
 */
export const palette = {
  bg: "#080a0b",
  surface: "#15191b",
  surface2: "#1b2022",
  border: "#2c3430",
  grid: "#232a27",
  primary: "#c8f53f",
  primaryLight: "#d5ff55",
  muted: "#9ca39f",
  fg: "#f4f6f1",
  gold: "#ff9f19",
  blue: "#38bdf8",
  green: "#4ade80",
  gray: "#94a3b8",
  red: "#f87171",
} as const;
