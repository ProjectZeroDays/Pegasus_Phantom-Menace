import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "wouter";
import { ChevronDown, ChevronRight, Shield, Smartphone, RefreshCw, X } from "lucide-react";
import { NAV_GROUPS } from "@/nav";
import { PEGASUS_VECTOR } from "@/lib/brand";
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
  const sidebarRef = useRef<HTMLElement>(null);
  const touchStartX = useRef<number>(0);

  useEffect(() => {
    window.localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapsed));
  }, [collapsed]);

  // Swipe gesture handling for mobile
  useEffect(() => {
    const sidebar = sidebarRef.current;
    if (!sidebar) return;

    const handleTouchStart = (e: TouchEvent) => {
      touchStartX.current = e.touches[0].clientX;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (touchStartX.current === 0) return;
      const deltaX = e.touches[0].clientX - touchStartX.current;
      // Only handle swipes from left edge (opening) or when sidebar is open (closing)
      const isOpen = sidebar.classList.contains("open");
      if ((!isOpen && deltaX > 0 && touchStartX.current < 30) || (isOpen && deltaX < 0)) {
        e.preventDefault();
      }
    };

    const handleTouchEnd = (e: TouchEvent) => {
      if (touchStartX.current === 0) return;
      const deltaX = e.changedTouches[0].clientX - touchStartX.current;
      const isOpen = sidebar.classList.contains("open");
      const threshold = 80;
      
      if (!isOpen && deltaX > threshold && touchStartX.current < 30) {
        // Swipe from left edge to open
        onNavigate?.(); // This will set open to true via the parent
      } else if (isOpen && deltaX < -threshold) {
        // Swipe left to close
        onNavigate?.(); // This will toggle/close
      }
      touchStartX.current = 0;
    };

    sidebar.addEventListener("touchstart", handleTouchStart, { passive: true });
    sidebar.addEventListener("touchmove", handleTouchMove, { passive: false });
    sidebar.addEventListener("touchend", handleTouchEnd, { passive: true });

    return () => {
      sidebar.removeEventListener("touchstart", handleTouchStart);
      sidebar.removeEventListener("touchmove", handleTouchMove);
      sidebar.removeEventListener("touchend", handleTouchEnd);
    };
  }, [onNavigate]);

  const toggle = (id: string) =>
    setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));

  const activeDevice = devices.find((d) => d.serial === activeSerial);

  return (
    <aside className={cn("sidebar", open && "open")}>
      <div style={{ padding: "16px 16px 12px", borderBottom: "1px solid var(--line-soft)" }}>
        <div className="row" style={{ gap: 10, alignItems: "center", justifyContent: "space-between" }}>
          <Link href="/" className="row" style={{ gap: 10, flex: 1 }} onClick={onNavigate}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 9,
                background: "linear-gradient(135deg,#0d2237,#06101c)",
                display: "grid",
                placeItems: "center",
                boxShadow: "0 4px 14px rgba(88,166,255,.35)",
                overflow: "hidden",
              }}
            >
              <img src={PEGASUS_VECTOR} alt="Pegasus" width={34} height={34} />
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
          {/* Mobile close button */}
          {open && (
            <Button
              variant="ghost"
              size="sm"
              className="sidebar-close-btn"
              onClick={onNavigate}
              aria-label="Close sidebar"
              style={{ padding: 4 }}
            >
              <X size={16} />
            </Button>
          )}
        </div>

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
          <div style={{display:'flex',gap:6,fontSize:10,color:'#a3e635'}}>
            <span title="VPN (default on)">🔒VPN</span>
            <span title="DNSCrypt (default on)">🔑DNS</span>
            <span title="Tor (default on)">🧅Tor</span>
            <span title="Proxy (default on)">🌐Proxy</span>
            <span title="Logs dashboard">📋Logs</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
