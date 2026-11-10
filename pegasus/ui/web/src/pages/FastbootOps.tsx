import { useCallback, useState } from "react";
import { HardDrive, Lock, ShieldOff, Smartphone, Wrench } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel } from "@/components/ui";
import { useApp } from "@/state/AppContext";

interface Engine {
  key: string;
  label: string;
  effects: string[];
}

interface State {
  adb: string;
  fastboot: string;
  manufacturer: string;
  samsung: boolean;
  root: boolean;
}

interface Frp {
  verdict: string;
  setup_complete: string | null;
  provisioned: string | null;
  frp_partition: string | null;
}

interface RootInfo {
  solution: string;
  uid0: boolean;
}

const ICONS: Record<string, React.ReactNode> = {
  bootloader: <Lock size={13} />,
  flash: <HardDrive size={13} />,
  verity: <ShieldOff size={13} />,
  frp: <ShieldOff size={13} />,
  root: <Wrench size={13} />,
  samsung: <Smartphone size={13} />,
};

export default function FastbootOps() {
  const { activeSerial } = useApp();
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [partition, setPartition] = useState("boot");
  const [path, setPath] = useState("");

  const { data: engineData } = useApi<{ engines: Engine[] }>("/fastboot/engines");
  const { data: state, refresh } = useApi<State>(
    activeSerial ? `/fastboot/${activeSerial}/state` : null,
  );
  const { data: frp, refresh: refreshFrp } = useApi<Frp>(
    activeSerial ? `/fastboot/${activeSerial}/frp` : null,
  );
  const { data: rootInfo } = useApi<RootInfo>(
    activeSerial ? `/fastboot/${activeSerial}/root/detect` : null,
  );

  const push = useCallback((line: string) => {
    setLog((prev) => [line, ...prev].slice(0, 40));
  }, []);

  const call = useCallback(
    async (effect: string, body?: Record<string, unknown>) => {
      if (!activeSerial) return;
      setBusy(effect);
      try {
        const res = await api.post<Record<string, unknown>>(
          `/fastboot/${activeSerial}/${effect}`,
          body ?? {},
        );
        push(`${effect}: ${JSON.stringify(res).slice(0, 260)}`);
      } catch (err) {
        push(`${effect}: error ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setBusy(null);
      }
    },
    [activeSerial, push],
  );

  const get = useCallback(
    async (effect: string) => {
      if (!activeSerial) return;
      setBusy(effect);
      try {
        const res = await api.get<Record<string, unknown>>(`/fastboot/${activeSerial}/${effect}`);
        push(`${effect}: ${JSON.stringify(res).slice(0, 260)}`);
      } catch (err) {
        push(`${effect}: error ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setBusy(null);
      }
    },
    [activeSerial, push],
  );

  if (!activeSerial) {
    return (
      <>
        <PageHeader title="Fastboot & FRP" subtitle="Bootloader, FRP and root actions" />
        <Panel>
          <Empty title="No device selected" detail="Pick a device on the Devices page first." />
        </Panel>
      </>
    );
  }

  const engines = engineData?.engines ?? [];
  const disabled = (effect: string) => busy !== null && busy !== effect;
  const fastbootUp = state?.fastboot === "fastboot";

  const control = (effect: string) => {
    switch (effect) {
      case "unlock":
        return <Button onClick={() => void call("unlock")} disabled={disabled("unlock")}>Unlock ladder</Button>;
      case "unlock-critical":
        return <Button variant="ghost" onClick={() => void call("unlock")} disabled={disabled("unlock")}>Critical</Button>;
      case "unlock-ability":
        return <Button variant="ghost" onClick={() => void get("unlock-ability")} disabled={disabled("unlock-ability")}>Ability</Button>;
      case "getvar":
        return <Button variant="ghost" onClick={() => void get("getvar?name=all")} disabled={disabled("getvar")}>getvar all</Button>;
      case "boot":
      case "init_boot":
      case "recovery":
      case "partition":
        return (
          <div className="row">
            <input value={partition} onChange={(e) => setPartition(e.target.value)}
              aria-label="partition" style={{ width: 92 }} />
            <input value={path} onChange={(e) => setPath(e.target.value)}
              placeholder="C:\path\image.img" aria-label="image path" />
            <Button onClick={() => void call("flash", { partition, path })}
              disabled={disabled("flash") || !path}>Flash</Button>
          </div>
        );
      case "vbmeta":
        return (
          <div className="row">
            <input value={path} onChange={(e) => setPath(e.target.value)}
              placeholder="vbmeta.img" aria-label="vbmeta path" />
            <Button onClick={() => void call("vbmeta", { path })} disabled={disabled("vbmeta") || !path}>Flash vbmeta</Button>
          </div>
        );
      case "temp-boot":
        return (
          <div className="row">
            <input value={path} onChange={(e) => setPath(e.target.value)}
              placeholder="boot.img" aria-label="boot path" />
            <Button onClick={() => void call("temp-boot", { path })} disabled={disabled("temp-boot") || !path}>Boot once</Button>
          </div>
        );
      case "disable-verity":
        return <Button onClick={() => void call("disable-verity")} disabled={disabled("disable-verity")}>Disable verity</Button>;
      case "current-slot":
        return <Button variant="ghost" onClick={() => void get("current-slot")} disabled={disabled("current-slot")}>Current</Button>;
      case "set-active":
        return (
          <div className="row">
            {["a", "b"].map((s) => (
              <Button key={s} variant="ghost" onClick={() => void call("set-active", { slot: s })}
                disabled={disabled("set-active")}>{s}</Button>
            ))}
          </div>
        );
      case "device-info":
        return <Button variant="ghost" onClick={() => void get("device-info")} disabled={disabled("device-info")}>OEM info</Button>;
      case "unlock-data":
        return <Button variant="ghost" onClick={() => void get("unlock-data")} disabled={disabled("unlock-data")}>Unlock data</Button>;
      case "carrier-unlock":
        return <Button onClick={() => void call("carrier-unlock")} disabled={disabled("carrier-unlock")}>Carrier unlock</Button>;
      case "cache":
      case "userdata":
        return (
          <div className="row">
            <Button variant="ghost" onClick={() => void call("erase", { target: "cache" })}
              disabled={disabled("erase")}>Erase cache</Button>
            <Button variant="ghost" onClick={() => void call("userdata")}
              disabled={disabled("userdata")}>Wipe data</Button>
          </div>
        );
      case "state":
        return <Button variant="ghost" onClick={() => refresh()}>Refresh</Button>;
      case "chain":
        return <Button onClick={() => void call("frp/chain")} disabled={disabled("frp/chain")}>Run FRP chain</Button>;
      case "play-protect":
        return <Button variant="ghost" onClick={() => void call("play-protect")} disabled={disabled("play-protect")}>Kill Play Protect</Button>;
      case "detect":
        return <Button variant="ghost" onClick={() => void get("root/detect")} disabled={disabled("root/detect")}>Detect root</Button>;
      case "modules":
        return <Button variant="ghost" onClick={() => void get("root/modules")} disabled={disabled("root/modules")}>Modules</Button>;
      case "denylist":
        return <Button variant="ghost" onClick={() => void get("root/denylist")} disabled={disabled("root/denylist")}>Denylist</Button>;
      case "install-module":
        return (
          <div className="row">
            <input value={path} onChange={(e) => setPath(e.target.value)}
              placeholder="module.zip" aria-label="module path" />
            <Button onClick={() => void call("root/install-module", { path })}
              disabled={disabled("root/install-module") || !path}>Install</Button>
          </div>
        );
      case "download-mode":
        return <Button onClick={() => void call("samsung/download-mode")} disabled={disabled("samsung/download-mode")}>Download mode</Button>;
      case "heimdall-flash":
        return (
          <div className="row">
            <Button onClick={() => void call("samsung/heimdall", { partition, path })}
              disabled={disabled("samsung/heimdall") || !path}>Heimdall flash</Button>
          </div>
        );
      default:
        return <Badge>{effect}</Badge>;
    }
  };

  return (
    <>
      <PageHeader
        title="Fastboot & FRP"
        subtitle={`Bootloader control for ${activeSerial}`}
        actions={
          <div className="row">
            <Badge tone={state?.adb === "device" ? "ok" : "dim"}>adb {state?.adb ?? "?"}</Badge>
            <Badge tone={fastbootUp ? "ok" : "dim"}>fastboot {state?.fastboot ?? "?"}</Badge>
            {rootInfo?.solution && rootInfo.solution !== "none" && (
              <Badge tone="warn">{rootInfo.solution}</Badge>
            )}
          </div>
        }
      />

      {!fastbootUp && (
        <Panel title="Not in fastboot">
          <p className="muted">
            Bootloader actions need the device in fastboot. FRP, root and Samsung actions work over adb.
          </p>
          <Button onClick={() => void call("reboot", { target: "bootloader" })}
            disabled={disabled("reboot")}>Reboot to bootloader</Button>
        </Panel>
      )}

      <Panel title="FRP verdict">
        <div className="grid-4">
          <div><div className="muted">State</div><div>{frp?.verdict ?? "—"}</div></div>
          <div><div className="muted">setup_complete</div><div>{frp?.setup_complete ?? "—"}</div></div>
          <div><div className="muted">device_provisioned</div><div>{frp?.provisioned ?? "—"}</div></div>
          <div><div className="muted">ro.frp.pst</div><div>{frp?.frp_partition ?? "—"}</div></div>
        </div>
        <div className="row" style={{ marginTop: 8 }}>
          <Button variant="ghost" onClick={() => refreshFrp()}>Re-read</Button>
        </div>
      </Panel>

      <div className="grid-2">
        {engines.map((engine) => (
          <Panel key={engine.key} title={engine.label}>
            <div className="muted" style={{ marginBottom: 8 }}>{ICONS[engine.key]}</div>
            <div className="stack">
              {engine.effects.map((effect) => (
                <div key={effect} className="row" style={{ gap: 8, alignItems: "center" }}>
                  <span className="muted" style={{ minWidth: 108 }}>{effect}</span>
                  {control(effect)}
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>

      <Panel title="Response log">
        {log.length === 0 ? <Empty title="No commands sent yet" /> : <pre className="log">{log.join("\n")}</pre>}
      </Panel>
    </>
  );
}
