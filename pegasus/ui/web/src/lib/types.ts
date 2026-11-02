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
