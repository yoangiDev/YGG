/**
 * Hex colours for the SVG charts: presentation attributes (stroke,
 * fill) don't accept var(). It mirrors the tokens of styles/index.css.
 *
 * `primary` is the interface accent (acid green) and represents the player in the
 * charts; the rest of the data colours keep their meaning.
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
  subtle: "#8d958f",
  red: "#f87171",
} as const;

/** Extra colours to tell many series apart at once (the kinds of moment, the gaps in a map): they are not interface tokens. */
export const categorical = {
  violet: "#c084fc",
  orange: "#fb923c",
  pink: "#f472b6",
  yellow: "#facc15",
  teal: "#2dd4bf",
  indigo: "#a78bfa",
  amber: "#f59e0b",
  sky: "#38bdf8",
  mint: "#34d399",
  periwinkle: "#818cf8",
  fuchsia: "#e879f9",
  rose: "#fb7185",
  tangerine: "#f97316",
  cornflower: "#60a5fa",
} as const;
