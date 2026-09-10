const LOCALE = "en-GB";
const MINUS = "−";

export function formatNumber(value: number, digits = 1): string {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: digits }).format(value);
}

/** +150 / −35 / 0: los diferenciales se leen mejor con signo explícito. */
export function formatSigned(value: number, digits = 0): string {
  const magnitude = formatNumber(Math.abs(value), digits);
  if (value > 0 && magnitude !== "0") return `+${magnitude}`;
  if (value < 0 && magnitude !== "0") return `${MINUS}${magnitude}`;
  return "0";
}

export function formatPercent(value: number, digits = 1): string {
  return `${formatNumber(value, digits)}%`;
}

/** 1845 → "30:45" */
export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

export function formatDate(value: string | Date): string {
  return new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short", year: "numeric" }).format(
    new Date(value),
  );
}

export function formatDateTime(value: string | Date): string {
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function timeAgo(value: string | Date, now: Date = new Date()): string {
  const seconds = Math.round((now.getTime() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

/** "2026-09-01" → segundos Unix UTC al inicio (o al final) de ese día. */
export function dateInputToUnix(value: string, endOfDay = false): number {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) throw new Error(`Invalid date: ${value}`);
  const time = endOfDay ? Date.UTC(year, month - 1, day, 23, 59, 59) : Date.UTC(year, month - 1, day);
  return Math.floor(time / 1000);
}

/** Date → "2026-09-01" (valor de un <input type="date">). */
export function toDateInput(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Algunos ratios llegan como fracción (0.62) y otros ya en porcentaje (62). */
export function asPercent(value: number): number {
  return Math.abs(value) <= 1 ? value * 100 : value;
}

/** Valor de una métrica con su unidad, con más decimales cuanto más pequeño es el número. */
export function formatMetric(value: number, unit = ""): string {
  const trimmed = unit.trim();
  if (trimmed === "%") return formatPercent(value);
  if (trimmed === "s") return formatDuration(value);
  const magnitude = Math.abs(value);
  const number = formatNumber(value, magnitude >= 100 ? 0 : magnitude >= 10 ? 1 : 2);
  return trimmed ? `${number} ${trimmed}` : number;
}
