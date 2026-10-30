import { useEffect, useState } from "react";
import { Link, useLocation } from "wouter";
import { ChevronDown, ChevronRight, Shield, Smartphone, RefreshCw } from "lucide-react";
import { NAV_GROUPS } from "@/nav";
import { useApp } from "@/state/AppContext";
import { cn } from "@/lib/utils";
import { Badge, Button } from "@/components/ui";

const COLLAPSE_KEY = "pegasus.nav.collapsed";

export function Sidebar({ onNavigate, open }: { onNavigate?: () => void; open?: boolean }) {
  const [location] = useLocation();
  const { devices, activeSerial, setActiveSerial, system, refreshDevices } = useApp();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => {
    try {
      return JSON.parse(window.localStorage.getItem(COLLAPSE_KEY) ?? "{}");
    } catch {
      return {};
    }
  });

  useEffect(() => {
    window.localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapsed));
  }, [collapsed]);

  const toggle = (id: string) =>
    setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));

  const activeDevice = devices.find((d) => d.serial === activeSerial);

  return (
    <aside className={cn("sidebar", open && "open")}>
      <div style={{ padding: "16px 16px 12px", borderBottom: "1px solid var(--line-soft)" }}>
        <Link href="/" className="row" style={{ gap: 10 }} onClick={onNavigate}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              background: "linear-gradient(135deg,#ff3d00,#bf3600)",
              display: "grid",
              placeItems: "center",
              boxShadow: "0 4px 14px rgba(255,61,0,.35)",
            }}
          >
            <Shield size={18} color="#0a0b0e" />
          </div>
          <div>
            <div
              className="mono"
              style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: ".16em", color: "#fff" }}
            >
              PEGASUS
            </div>
            <div className="tiny mute" style={{ letterSpacing: ".1em" }}>
              PHANTOM MENACE v{system?.workspace.version ?? "2.0.0"}
            </div>
          </div>
        </Link>

        <div style={{ marginTop: 14 }}>
          <div className="field-label" style={{ marginBottom: 6 }}>
            Active device
          </div>
          <div className="row" style={{ gap: 6 }}>
            <select
              className="select"
              value={activeSerial ?? ""}
              onChange={(event) => setActiveSerial(event.target.value)}
            >
              {devices.length === 0 && <option value="">no devices attached</option>}
              {devices.map((device) => (
                <option key={device.serial} value={device.serial}>
                  {device.label || device.model || device.serial}
                </option>
              ))}
            </select>
            <Button size="sm" onClick={() => void refreshDevices()} title="Refresh devices">
              <RefreshCw size={13} />
            </Button>
          </div>
          <div className="row tiny mute" style={{ marginTop: 7, gap: 6 }}>
            <Smartphone size={11} />
            <span className="td-truncate" style={{ maxWidth: 190 }}>
              {activeSerial ? activeSerial : "—"}
            </span>
            {activeDevice?.state === "device" ? (
              <Badge tone="ok">online</Badge>
            ) : activeSerial ? (
              <Badge tone="warn">{activeDevice?.state ?? "unknown"}</Badge>
            ) : null}
          </div>
        </div>
      </div>

      <nav className="sidebar-scroll">
        {NAV_GROUPS.map((group) => {
          const isCollapsed = collapsed[group.id];
          const hasActive = group.items.some((item) => item.path === location);
          return (
            <div className="nav-group" key={group.id}>
              <button className="nav-head" onClick={() => toggle(group.id)}>
                <span style={{ color: hasActive ? "var(--primary)" : undefined }}>
                  {group.label}
                </span>
                {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
              </button>
              {!isCollapsed && (
                <div>
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = location === item.path;
                    return (
                      <Link
                        key={item.path}
                        href={item.path}
                        className={cn("nav-link", active && "active")}
                        onClick={onNavigate}
                      >
                        <Icon size={14} />
                        <span>{item.label}</span>
                        {item.badge ? <span className="nav-badge">{item.badge}</span> : null}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div
        style={{
          padding: "10px 14px 14px",
          borderTop: "1px solid var(--line-soft)",
          fontSize: 10.5,
          color: "var(--ink-mute)",
          lineHeight: 1.7,
        }}
      >
        <div className="row" style={{ gap: 6 }}>
          <span className={`dot ${system ? "ok" : "err"}`} />
          <span>{system ? "API connected" : "API offline"}</span>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <span className={`dot ${system?.workspace.aiConfigured ? "ok" : "warn"}`} />
          <span>AI: {system?.workspace.aiConfigured ? system.workspace.aiModel : "unconfigured"}</span>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <span className="dot idle" />
          <span>{system?.plugins ?? 0} plugins · {system?.commands ?? 0} commands</span>
        </div>
      </div>
    </aside>
  );
}
