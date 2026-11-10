import { useCallback, useState } from "react";
import { Flashlight, Radio, Smartphone, Volume2, Zap } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel } from "@/components/ui";
import { useApp } from "@/state/AppContext";

interface Engine {
  key: string;
  label: string;
  effects: string[];
}

interface State {
  battery?: string | null;
  thermal?: string | null;
  brightness?: string | null;
  ringer?: string | null;
}

const ICONS: Record<string, React.ReactNode> = {
  haptic: <Zap size={13} />,
  display: <Flashlight size={13} />,
  audio: <Volume2 size={13} />,
  radio: <Radio size={13} />,
  power: <Smartphone size={13} />,
};

export default function PhysicalOps() {
  const { activeSerial } = useApp();
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [ms, setMs] = useState(400);
  const [level, setLevel] = useState(128);
  const [volume, setVolume] = useState(7);
  const [text, setText] = useState("hello from pegasus");
  const [hz, setHz] = useState(880);
  const [tapX, setTapX] = useState(540);
  const [tapY, setTapY] = useState(1200);

  const { data: engineData } = useApi<{ engines: Engine[] }>("/physical/engines");
  const { data: state, refresh } = useApi<State>(
    activeSerial ? `/physical/${activeSerial}/state` : null,
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
          `/physical/${activeSerial}/${effect}`,
          body ?? {},
        );
        push(`${effect}: ${JSON.stringify(res).slice(0, 220)}`);
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
        <PageHeader title="Physical Ops" subtitle="Direct effect control over the selected handset" />
        <Panel>
          <Empty title="No device selected" detail="Pick a device on the Devices page first." />
        </Panel>
      </>
    );
  }

  const engines = engineData?.engines ?? [];
  const disabled = (effect: string) => busy !== null && busy !== effect;

  const control = (effect: string) => {
    switch (effect) {
      case "vibrate":
        return (
          <div className="row">
            <input type="number" value={ms} min={50} max={5000}
              onChange={(e) => setMs(Number(e.target.value))} aria-label="duration ms" />
            <Button onClick={() => void call("vibrate", { ms })} disabled={disabled("vibrate")}>
              Buzz
            </Button>
          </div>
        );
      case "torch":
        return (
          <div className="row">
            <Button onClick={() => void call("torch", { on: true })} disabled={disabled("torch")}>On</Button>
            <Button variant="ghost" onClick={() => void call("torch", { on: false })} disabled={disabled("torch")}>Off</Button>
          </div>
        );
      case "brightness":
        return (
          <div className="row">
            <input type="range" min={0} max={255} value={level}
              onChange={(e) => setLevel(Number(e.target.value))} aria-label="brightness" />
            <span className="muted">{level}</span>
            <Button onClick={() => void call("brightness", { level })} disabled={disabled("brightness")}>Set</Button>
          </div>
        );
      case "screen":
        return (
          <div className="row">
            {["on", "off", "toggle"].map((a) => (
              <Button key={a} variant="ghost" onClick={() => void call("screen", { action: a })}
                disabled={disabled("screen")}>{a}</Button>
            ))}
          </div>
        );
      case "rotate":
        return (
          <div className="row">
            {[0, 1, 2, 3].map((r) => (
              <Button key={r} variant="ghost" onClick={() => void call("rotate", { rotation: r })}
                disabled={disabled("rotate")}>{r * 90}°</Button>
            ))}
          </div>
        );
      case "volume":
        return (
          <div className="row">
            <input type="range" min={0} max={15} value={volume}
              onChange={(e) => setVolume(Number(e.target.value))} aria-label="volume" />
            <span className="muted">{volume}</span>
            <Button onClick={() => void call("volume", { level: volume })} disabled={disabled("volume")}>Set</Button>
          </div>
        );
      case "ringer":
        return (
          <div className="row">
            {["silent", "vibrate", "normal", "alarm"].map((label, m) => (
              <Button key={label} variant="ghost" onClick={() => void call("ringer", { mode: m })}
                disabled={disabled("ringer")}>{label}</Button>
            ))}
          </div>
        );
      case "media":
        return (
          <div className="row">
            {["playpause", "next", "prev"].map((a) => (
              <Button key={a} variant="ghost" onClick={() => void call("media", { action: a })}
                disabled={disabled("media")}>{a}</Button>
            ))}
          </div>
        );
      case "tts":
        return (
          <div className="row">
            <input value={text} onChange={(e) => setText(e.target.value)} aria-label="speech text" />
            <Button onClick={() => void call("tts", { text })} disabled={disabled("tts")}>Speak</Button>
          </div>
        );
      case "beep":
        return (
          <div className="row">
            <input type="number" value={hz} min={100} max={8000}
              onChange={(e) => setHz(Number(e.target.value))} aria-label="tone hz" />
            <Button onClick={() => void call("beep", { hz })} disabled={disabled("beep")}>Beep</Button>
          </div>
        );
      case "airplane":
      case "wifi":
      case "bluetooth":
      case "gps":
        return (
          <div className="row">
            <Button onClick={() => void call(effect, { on: true })} disabled={disabled(effect)}>On</Button>
            <Button variant="ghost" onClick={() => void call(effect, { on: false })} disabled={disabled(effect)}>Off</Button>
          </div>
        );
      case "text":
        return (
          <div className="row">
            <input value={text} onChange={(e) => setText(e.target.value)} aria-label="input text" />
            <Button onClick={() => void call("input/text", { text })} disabled={disabled("input/text")}>Type</Button>
          </div>
        );
      case "key":
        return (
          <div className="row">
            {[3, 4, 66, 67, 187].map((k) => (
              <Button key={k} variant="ghost" onClick={() => void call("input/key", { key: k })}
                disabled={disabled("input/key")}>{k}</Button>
            ))}
          </div>
        );
      case "tap":
        return (
          <div className="row">
            <input type="number" value={tapX} onChange={(e) => setTapX(Number(e.target.value))} aria-label="x" />
            <input type="number" value={tapY} onChange={(e) => setTapY(Number(e.target.value))} aria-label="y" />
            <Button onClick={() => void call("input/tap", { x: tapX, y: tapY })} disabled={disabled("input/tap")}>Tap</Button>
          </div>
        );
      case "swipe":
        return (
          <Button onClick={() => void call("input/swipe", { x1: 540, y1: 1600, x2: 540, y2: 400 })}
            disabled={disabled("input/swipe")}>Swipe up</Button>
        );
      case "wake":
      case "sleep":
      case "lock":
      case "unlock":
        return (
          <Button onClick={() => void call(effect)} disabled={disabled(effect)}>{effect}</Button>
        );
      case "reboot":
        return (
          <div className="row">
            {["", "recovery", "bootloader"].map((mode) => (
              <Button key={mode || "system"} variant="ghost"
                onClick={() => void call("reboot", { mode })} disabled={disabled("reboot")}>
                {mode || "system"}
              </Button>
            ))}
          </div>
        );
      case "state":
      case "thermal":
      case "sensors":
        return <Button variant="ghost" onClick={() => refresh()}>Refresh</Button>;
      case "screenshot":
        return <Button onClick={() => void call("screenshot")} disabled={disabled("screenshot")}>Capture</Button>;
      case "record":
        return (
          <div className="row">
            <Button onClick={() => void call("record", { action: "start" })} disabled={disabled("record")}>Start</Button>
            <Button variant="ghost" onClick={() => void call("record", { action: "stop" })} disabled={disabled("record")}>Stop</Button>
          </div>
        );
      default:
        return <Badge>{effect}</Badge>;
    }
  };

  return (
    <>
      <PageHeader
        title="Physical Ops"
        subtitle={`Effect control for ${activeSerial}`}
        actions={<Badge tone="dim">{engines.length} engines</Badge>}
      />

      <Panel title="Live state">
        <div className="grid-4">
          <div><div className="muted">Battery</div><div>{(state?.battery ?? "—").split("\n")[1] ?? "—"}</div></div>
          <div><div className="muted">Brightness</div><div>{state?.brightness ?? "—"}</div></div>
          <div><div className="muted">Ringer mode</div><div>{state?.ringer ?? "—"}</div></div>
          <div><div className="muted">Thermal</div><div>{state?.thermal ? "reported" : "—"}</div></div>
        </div>
      </Panel>

      <div className="grid-2">
        {engines.map((engine) => (
          <Panel key={engine.key} title={engine.label}>
            <div className="muted" style={{ marginBottom: 8 }}>{ICONS[engine.key]}</div>
            <div className="stack">
              {engine.effects.map((effect) => (
                <div key={effect} className="row" style={{ gap: 8, alignItems: "center" }}>
                  <span className="muted" style={{ minWidth: 92 }}>{effect}</span>
                  {control(effect)}
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>

      <Panel title="Response log">
        {log.length === 0 ? (
          <Empty title="No commands sent yet" />
        ) : (
          <pre className="log">{log.join("\n")}</pre>
        )}
      </Panel>
    </>
  );
}
