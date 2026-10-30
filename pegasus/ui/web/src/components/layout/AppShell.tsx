import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { Menu, Terminal as TerminalIcon, Activity, CircleDot } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { JobDrawer } from "@/components/JobDrawer";
import { useApp } from "@/state/AppContext";
import { ALL_NAV_ITEMS } from "@/nav";
import { Button } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { Job } from "@/lib/types";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const { system, activeSerial, connected } = useApp();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { data: jobData } = useApi<{ jobs: Job[]; stats: Record<string, number> }>("/jobs?limit=5", {
    interval: 5000,
  });

  useEffect(() => {
    setMenuOpen(false);
  }, [location]);

  const current = ALL_NAV_ITEMS.find((item) => item.path === location);
  const activeJobs = (jobData?.stats?.running ?? 0) + (jobData?.stats?.queued ?? 0);

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      {menuOpen && (
        <div
          onClick={() => setMenuOpen(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(4,6,9,.55)", zIndex: 29 }}
        />
      )}

      <div className="main-col">
        <header className="topbar">
          <div className="row" style={{ gap: 12 }}>
            <Button
              variant="ghost"
              size="sm"
              className="menu-toggle"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label="Toggle navigation"
            >
              <Menu size={16} />
            </Button>
            <div>
              <div className="mono" style={{ fontSize: 12, letterSpacing: ".13em", color: "#fff" }}>
                {current?.label?.toUpperCase() ?? "MISSION CONTROL"}
              </div>
              <div className="tiny mute">
                {activeSerial ? `device: ${activeSerial}` : "no device selected"} ·{" "}
                {connected ? "adb link up" : "adb link down"}
              </div>
            </div>
          </div>

          <div className="row" style={{ gap: 8 }}>
            <span className="badge badge-dim" title="Plugin count">
              <CircleDot size={10} /> {system?.plugins ?? 0} plugins
            </span>
            <span className="badge badge-dim" title="Command count">
              <Activity size={10} /> {system?.commands ?? 0} commands
            </span>
            <Button size="sm" variant="ghost" onClick={() => setDrawerOpen(true)}>
              <TerminalIcon size={13} />
              <span>Jobs</span>
              {activeJobs > 0 && <span className="badge badge-primary">{activeJobs}</span>}
            </Button>
          </div>
        </header>

        <main className="content">{children}</main>

        <footer className="bottombar">
          <div className="row" style={{ gap: 16 }}>
            <span className="row" style={{ gap: 6 }}>
              <span className={`dot ${system ? "ok" : "err"}`} /> API {system ? "operational" : "offline"}
            </span>
            <span className="row" style={{ gap: 6 }}>
              <span className="dot idle" /> DB {system?.workspace.database ?? "—"}
            </span>
            <span className="row" style={{ gap: 6 }}>
              <span className={`dot ${system?.workspace.aiConfigured ? "ok" : "warn"}`} />
              AI {system?.workspace.aiConfigured ? "configured" : "unconfigured"}
            </span>
            <span className="row" style={{ gap: 6 }}>
              <span className="dot idle" /> MSF {system?.workspace.metasploit ?? "—"}
            </span>
          </div>
          <div className="row" style={{ gap: 16 }}>
            <span>{system?.environment.hostname ?? "host"}</span>
            <span>{system?.environment.localIp ?? "—"}</span>
            <span className="orange">authorized testing only</span>
          </div>
        </footer>
      </div>

      <JobDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
