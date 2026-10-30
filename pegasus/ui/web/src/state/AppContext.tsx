import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { DeviceRecord, SystemInfo } from "@/lib/types";

interface AppState {
  devices: DeviceRecord[];
  activeSerial: string | null;
  setActiveSerial: (serial: string) => void;
  system: SystemInfo | null;
  refreshDevices: () => Promise<void>;
  refreshSystem: () => Promise<void>;
  connected: boolean;
}

const AppContext = createContext<AppState | null>(null);

const STORAGE_KEY = "pegasus.activeSerial";

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [activeSerial, setActiveSerialState] = useState<string | null>(
    () => window.localStorage.getItem(STORAGE_KEY),
  );
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [connected, setConnected] = useState(false);

  const refreshDevices = useCallback(async () => {
    try {
      const data = await api.get<{ devices: DeviceRecord[]; count: number }>("/devices");
      setDevices(data.devices);
      setConnected(true);
      if (data.devices.length && !data.devices.some((d) => d.serial === activeSerial)) {
        setActiveSerialState(data.devices[0].serial);
        window.localStorage.setItem(STORAGE_KEY, data.devices[0].serial);
      }
    } catch {
      setConnected(false);
    }
  }, [activeSerial]);

  const refreshSystem = useCallback(async () => {
    try {
      setSystem(await api.get<SystemInfo>("/system"));
    } catch {
      setSystem(null);
    }
  }, []);

  const setActiveSerial = useCallback((serial: string) => {
    setActiveSerialState(serial);
    window.localStorage.setItem(STORAGE_KEY, serial);
  }, []);

  useEffect(() => {
    void refreshDevices();
    void refreshSystem();
    const deviceTimer = window.setInterval(() => void refreshDevices(), 20000);
    const systemTimer = window.setInterval(() => void refreshSystem(), 30000);
    return () => {
      window.clearInterval(deviceTimer);
      window.clearInterval(systemTimer);
    };
  }, [refreshDevices, refreshSystem]);

  const value = useMemo<AppState>(
    () => ({
      devices,
      activeSerial,
      setActiveSerial,
      system,
      refreshDevices,
      refreshSystem,
      connected,
    }),
    [devices, activeSerial, setActiveSerial, system, refreshDevices, refreshSystem, connected],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}

/** Convenience: active device serial, or null with a banner handled by pages. */
export function useActiveDevice(): { serial: string | null; device: DeviceRecord | null } {
  const { activeSerial, devices } = useApp();
  return {
    serial: activeSerial,
    device: devices.find((d) => d.serial === activeSerial) ?? null,
  };
}
