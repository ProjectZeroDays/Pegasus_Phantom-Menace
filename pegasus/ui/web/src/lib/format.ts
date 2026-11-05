/** Display formatters. All tolerate null, undefined and non-numeric input. */

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"] as const;

function num(value: unknown): number | null {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatBytes(value: unknown, digits = 1): string {
  const bytes = num(value);
  if (bytes === null || bytes < 0) return "—";
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  let scale = 0;
  let size = bytes;
  while (size >= 1024 && scale < BYTE_UNITS.length - 1) {
    size /= 1024;
    scale += 1;
  }
  return `${size.toFixed(digits)} ${BYTE_UNITS[scale]}`;
}

export function formatNumber(value: unknown, digits = 0): string {
  const parsed = num(value);
  if (parsed === null) return "—";
  return parsed.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function toDate(value: unknown): Date | null {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "number" || (typeof value === "string" && /^\d+$/.test(value))) {
    const numeric = Number(value);
    const ms = numeric > 1e11 ? numeric : numeric * 1000;
    const date = new Date(ms);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatTime(value: unknown): string {
  const date = toDate(value);
  return date ? date.toLocaleTimeString() : "—";
}

export function formatDateTime(value: unknown): string {
  const date = toDate(value);
  if (!date) return "—";
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

/** Duration from milliseconds. */
export function formatMs(value: unknown): string {
  const ms = num(value);
  if (ms === null || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return formatDuration(ms / 1000);
}

/** Duration from seconds. */
export function formatDuration(value: unknown): string {
  const seconds = num(value);
  if (seconds === null || seconds < 0) return "—";
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${rest}s`;
  return `${rest}s`;
}

/** Relative time from an epoch value in milliseconds. */
export function timeAgo(value: unknown): string {
  const date = toDate(value);
  if (!date) return "—";
  const delta = Math.round((Date.now() - date.getTime()) / 1000);
  if (delta < 0) return "just now";
  if (delta < 45) return "just now";
  if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
  if (delta < 2592000) return `${Math.round(delta / 86400)}d ago`;
  return date.toLocaleDateString();
}

export function titleCase(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function initials(value: unknown): string {
  if (value === null || value === undefined) return "?";
  const words = String(value).trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

const SEVERITY_TONES: Record<string, string> = {
  critical: "err",
  high: "warn",
  medium: "info",
  moderate: "info",
  low: "dim",
  info: "dim",
  none: "dim",
};

export function severityClass(value: unknown): string {
  const key = String(value ?? "").toLowerCase().trim();
  return SEVERITY_TONES[key] ?? "dim";
}
