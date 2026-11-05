/** Device telemetry hook: reads the latest sample, triggers collection. */
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
