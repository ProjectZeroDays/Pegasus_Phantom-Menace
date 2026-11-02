/** Formatting helpers shared across the Pegasus web GUI. */

export function formatBytes(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(digits)} ${units[i]}`;
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat().format(n);
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rs = Math.round(s % 60);
  if (m < 60) return `${m}m ${rs}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function formatMs(ms: number | null | undefined): string {
  return formatDuration(ms);
}

export function formatTime(t: number | string | null | undefined): string {
  const d = toDate(t);
  return d ? d.toLocaleTimeString() : "—";
}

export function formatDateTime(t: number | string | null | undefined): string {
  const d = toDate(t);
  if (!d) return "—";
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
}

export function timeAgo(t: number | string | Date | null | undefined): string {
  const d = toDate(t);
  if (!d) return "—";
  const diff = Date.now() - d.getTime();
  if (diff < 0) return formatDateTime(d as any);
  const s = Math.floor(diff / 1000);
  if (s < 10) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

export function titleCase(s: string | null | undefined): string {
  if (!s) return "";
  return String(s)
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .map((w) => (w.length ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

export function initials(s: string | null | undefined): string {
  if (!s) return "?";
  return String(s)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

export function severityClass(sev: string | null | undefined): string {
  const s = (sev ?? "").toLowerCase();
  if (["critical", "high", "9", "10"].includes(s)) return "text-red-400";
  if (["medium", "moderate"].includes(s)) return "text-amber-400";
  if (["low"].includes(s)) return "text-sky-400";
  return "text-slate-400";
}

function toDate(t: any): Date | null {
  if (t === null || t === undefined) return null;
  if (t instanceof Date) return t;
  if (typeof t === "number") {
    // seconds vs milliseconds
    return new Date(t < 1e12 ? t * 1000 : t);
  }
  const s = String(t);
  if (/^\d+(\.\d+)?$/.test(s)) {
    const n = Number(s);
    return new Date(n < 1e12 ? n * 1000 : n);
  }
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}
