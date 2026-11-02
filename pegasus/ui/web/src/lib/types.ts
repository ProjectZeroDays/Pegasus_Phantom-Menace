/** Shared API types for the Pegasus web GUI. */

export type Phase =
  | "idle" | "discover" | "triage" | "craft" | "deliver"
  | "listen" | "post" | "notify" | "deciding" | "maintain" | "wipe" | "done" | "failed";

export interface Target {
  serial: string; transport: "usb" | "wifi"; score: number;
  vector: string | null; sdk?: string; model?: string; notes: string[];
}

export interface Run {
  id: string; phase: Phase; targets: Target[];
  session: Record<string, unknown>; decision: string | null;
  artifacts: Record<string, string>; log: string[];
}

export interface Receipt {
  ts: number; channel: string; kind: string; target: string;
  via: "sent" | "link" | "error"; ref: string | null; error: string | null;
}

export interface ChannelHealth { state: string; kinds: string[]; max_mb: number; reason: string; }

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Job {
  id: string;
  kind: string;
  title: string;
  status: JobStatus;
  progress: number;
  /** Unix seconds. */
  createdAt: number;
  startedAt?: number | null;
  finishedAt?: number | null;
  durationMs: number | null;
  error?: string | null;
  output?: string;
  result?: unknown;
  meta?: Record<string, unknown>;
  cancelRequested?: boolean;
}

// ---------------------------------------------------------------------------
// Devices
// ---------------------------------------------------------------------------

export interface DeviceRecord {
  serial: string;
  state: string;
  model?: string | null;
  product?: string | null;
  device?: string | null;
  transport?: string | null;
  isNetwork?: boolean;
  label?: string | null;
  manufacturer?: string | null;
  androidVersion?: string | null;
  apiLevel?: number | null;
  batteryLevel?: number | null;
  isRooted?: boolean;
}

export interface DeviceNotes {
  label?: string;
  group?: string;
  notes?: string;
}

export interface DeviceDetail extends DeviceRecord {
  manufacturer: string;
  androidVersion: string;
  apiLevel: number;
  securityPatch: string;
  buildId: string;
  buildType: string;
  buildTags: string;
  abi: string;
  fingerprint: string;
  batteryLevel: number | null;
  isRooted: boolean;
  storageTotal: number | null;
  storageFree: number | null;
  properties: Record<string, string>;
  notes?: DeviceNotes;
}

export interface DashboardCounts {
  contacts?: number;
  messages?: number;
  calls?: number;
  browserEntries?: number;
  photos?: number;
  apps?: number;
  locations?: number;
  geofences?: number;
}

export interface DashboardSummary {
  counts: DashboardCounts;
}

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------

export interface SystemWorkspace {
  workspace: string;
  database: string;
  databasePath: string;
  reportsDir: string;
  payloadsDir: string;
  logsDir: string;
  aiConfigured: boolean;
  aiModel: string;
  metasploit: string;
  version: string;
}

export interface SystemEnvironment {
  python: string;
  platform: string;
  system: string;
  release: string;
  machine: string;
  processor: string;
  hostname: string;
  localIp: string;
  pid: number;
  cwd: string;
}

export interface SystemComponent {
  name: string;
  status: string;
  detail: string;
}

export interface SystemInfo {
  plugins: number;
  commands: number;
  workspace: SystemWorkspace;
  environment: SystemEnvironment;
  components: SystemComponent[];
  health?: HealthInfo;
}

export interface HealthInfo {
  status: string;
  uptimeSeconds: number;
}

export interface ToolStatus {
  key: string;
  label: string;
  purpose: string;
  required: "yes" | "optional" | string;
  available: boolean;
  path?: string | null;
  version?: string | null;
}

export interface ListenerRow {
  host: string;
  port: number;
  open: boolean;
}

// ---------------------------------------------------------------------------
// Plugins & commands
// ---------------------------------------------------------------------------

export interface PluginCommand {
  name: string;
  description: string;
}

export interface PluginComponent {
  name: string;
  title: string;
  path: string;
}

export interface PluginInfo {
  name: string;
  version: string;
  description: string;
  category: string;
  initialized: boolean;
  tags: string[];
  author?: string | null;
  commands: PluginCommand[];
  components: PluginComponent[];
}

export interface CommandInfo {
  name: string;
  description: string;
  plugin: string;
  aliases: string[];
  category?: string;
}

export interface SlashCommandInfo {
  name: string;
  description: string;
  category: string;
  enabled: boolean;
}

// ---------------------------------------------------------------------------
// Payloads & reports
// ---------------------------------------------------------------------------

export interface PayloadFile {
  name: string;
  path: string;
  extension: string;
  sizeBytes: number;
  createdAt: number | string;
}

export interface ReportFile {
  name: string;
  format: string;
  sizeBytes: number;
  createdAt: number | string;
}

// ---------------------------------------------------------------------------
// Workflows & CVE data
// ---------------------------------------------------------------------------

export interface WorkflowHistoryEntry {
  run_id?: string;
  target?: string | null;
  category?: string | null;
  stages?: unknown[];
  overall_success?: boolean;
  total_duration_ms?: number | null;
  start_time?: number | string | null;
}

export interface CveEntry {
  id: string;
  severity: string;
  cvss: number;
  affected_api_min: number | string;
  affected_api_max: number | string;
  patch_level: string;
  description: string;
}

// ---------------------------------------------------------------------------
// Events & telemetry rows
// ---------------------------------------------------------------------------

export interface EventRow {
  id: string;
  /** Unix seconds (may arrive as a numeric string). */
  at: number | string;
  kind: string;
  title: string;
  detail?: string;
  level?: string;
}

export interface ActivityRow {
  id: number;
  app: string;
  durationSeconds: number;
  startedAt?: string | null;
}

export interface AppRow {
  id: number;
  name: string;
  packageName: string;
  path: string;
  version: string;
}

export interface BrowserRow {
  id: number;
  url: string;
  title: string;
  visitCount: number;
  lastVisitedAt?: number | string | null;
}

export interface CallRow {
  id: number;
  phone: string;
  name: string;
  callType: string;
  durationSeconds: number;
  calledAt?: number | string | null;
}

export interface ContactRow {
  id: number;
  name: string;
  phones: string[];
  emails: string[];
}

export interface KeylogRow {
  id: number;
  app: string;
  text: string;
  recordedAt: number | string;
}

export interface LocationRow {
  id: number;
  lat: number;
  lng: number;
  address: string;
  city?: string | null;
  source?: string | null;
  recordedAt?: number | string | null;
}

export interface PhotoRow {
  id: number;
  name: string;
  url: string;
  thumbnailUrl: string;
  sizeBytes: number;
  mimeType: string;
  takenAt?: number | string | null;
}

export interface VideoRow extends PhotoRow {
  durationSeconds: number;
}

export interface SmsRow {
  id: number;
  address: string;
  body: string;
  direction: string;
  type?: string;
  read: boolean;
  sentAt?: number | string | null;
}

export interface WifiRow {
  id: number;
  ssid: string;
  bssid?: string | null;
  isConnected: boolean;
  lastSeenAt?: number | string | null;
}

// ---------------------------------------------------------------------------
// Campaigns, geofences & keywords
// ---------------------------------------------------------------------------

export interface CampaignRow {
  campaign_id?: string;
  name?: string;
  client?: string;
  status?: string;
  created_at?: number | string | null;
  target_count?: number;
  authorization_level?: string;
}

export interface Geofence {
  id: number;
  deviceSerial?: string;
  name: string;
  lat: number;
  lng: number;
  radiusMeters: number;
  isActive: boolean;
  createdAt: number | string;
}

export interface Keyword {
  id: number;
  keyword: string;
  hitCount: number;
  lastHitAt?: number | string | null;
  createdAt: number | string;
}

export interface KeywordMatch {
  source: string;
  text: string;
}

export interface KeywordHit {
  id: number;
  keyword: string;
  matchCount: number;
  matches: KeywordMatch[];
}
