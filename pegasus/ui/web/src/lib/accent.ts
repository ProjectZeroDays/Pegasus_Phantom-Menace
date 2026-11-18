/**
 * Live accent colour.
 *
 * The accent is a free hex code.  It is kept in localStorage so it survives a
 * reload, mirrored to the backend so it follows the operator between hosts,
 * and applied by writing the signal tokens on the root element - the whole
 * theme reads them, so no component needs to know about the accent.
 */

const KEY = "pegasus.accent";

export function applyAccent(hex: string): void {
  const clean = (hex || "").trim();
  if (!/^#[0-9a-fA-F]{6}$/.test(clean)) return;
  const root = document.documentElement;
  root.style.setProperty("--primary", clean);
  root.style.setProperty("--color-primary", clean);
  root.style.setProperty("--accent-contrast", "#04102e");
  root.style.setProperty("--color-accent-contrast", "#04102e");
}

export function getAccent(): string {
  try {
    return localStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}

export function setAccent(hex: string): void {
  const clean = (hex || "").trim();
  if (!/^#[0-9a-fA-F]{6}$/.test(clean)) return;
  try {
    localStorage.setItem(KEY, clean);
  } catch {
    /* storage unavailable - the colour still applies for this session */
  }
  applyAccent(clean);
  // best-effort mirror to the backend; the console works without it
  void fetch("/api/settings/accent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accent: clean }),
  }).catch(() => undefined);
}
