import { useCallback, useState } from "react";
import { api, useApi } from "@/lib/api";
import type { Job } from "@/lib/types";
import { useActiveDevice } from "@/state/AppContext";

/** Fetch a telemetry collection for the active device. */
export function useTelemetry<T>(kind: string, refreshMs?: number) {
  const { serial } = useActiveDevice();
  const [nonce, setNonce] = useState(0);
  const path = serial ? `/devices/${encodeURIComponent(serial)}/telemetry/${kind}` : null;
  const state = useApi<T>(path, { interval: refreshMs, deps: [nonce] });

  const refreshLive = useCallback(async () => {
    if (!serial) return null;
    const data = await api.post<{ job: Job }>(`/devices/${encodeURIComponent(serial)}/collect`, {
      kinds: [kind],
    });
    return data.job;
  }, [kind, serial]);

  return {
    ...state,
    serial,
    burst: () => setNonce((n) => n + 1),
    collect: refreshLive,
  };
}

export function useDeviceSerial(): string | null {
  const { serial } = useActiveDevice();
  return serial;
}
