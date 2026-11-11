import { useEffect, useState } from "react";
import { Activity, Globe, Lock, Network, RefreshCw, Server, Shield, Wifi } from "lucide-react";
import { useApp } from "@/state/AppContext";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat, Terminal } from "@/components/ui";

interface NetStatus {
  externalIp: string;
  vpn: boolean;
  dnscrypt: boolean;
  proxy: boolean;
  proxychains: boolean;
  socks5: boolean;
  tor: boolean;
  noip: boolean;
  ssl: boolean;
  cert: string;
}

export default function NetworkDashboard() {
  const { system } = useApp();
  const [status, setStatus] = useState<NetStatus>({
    externalIp: "—",
    vpn: true,
    dnscrypt: true,
    proxy: false,
    proxychains: false,
    socks5: false,
    tor: false,
    noip: false,
    ssl: true,
    cert: "self-signed",
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const netInfo = useApi<{ ip: string; hostname: string; city: string; country: string; org: string }>("/network/info", { interval: 30000 });

  useEffect(() => {
    if (netInfo.data?.ip) setStatus((s) => ({ ...s, externalIp: netInfo.data!.ip }));
  }, [netInfo.data]);

  const toggle = async (key: keyof NetStatus) => {
    setBusy(key);
    setResult(null);
    try {
      await api.post(`/network/scan`, { key, value: !status[key] });
      setStatus((s) => ({ ...s, [key]: !s[key] }));
      setResult(`${key} toggled`);
    } catch (e: any) {
      setResult(`error: ${e?.message ?? "failed"}`);
    } finally {
      setBusy(null);
    }
  };

  const runQuery = async (q: string) => {
    setBusy("query");
    setResult(null);
    try {
      const r = await api.post<{ result: string }>("/network/query", { query: q });
      setResult(r.result);
    } catch (e: any) {
      setResult(`error: ${e?.message ?? "failed"}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Network Dashboard"
        subtitle="Monitor, configure and manage external IPv4, DNSCrypt, VPN, proxy chains, Tor, No-IP DDNS, SSL & certificates"
        actions={<Button size="sm" onClick={() => void netInfo.refresh()}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={status.externalIp} label="External IPv4" tone="ok" />
        <Stat value={status.vpn ? "ON" : "OFF"} label="VPN" tone={status.vpn ? "ok" : "warn"} />
        <Stat value={status.dnscrypt ? "ON" : "OFF"} label="DNSCrypt" tone={status.dnscrypt ? "ok" : "warn"} />
        <Stat value={status.tor ? "ON" : "OFF"} label="Tor" tone={status.tor ? "ok" : "warn"} />
        <Stat value={status.proxy ? "ON" : "OFF"} label="Proxy" tone={status.proxy ? "ok" : "warn"} />
        <Stat value={status.noip ? "ON" : "OFF"} label="No-IP DDNS" tone={status.noip ? "ok" : "warn"} />
      </div>

      <div className="grid-2">
        <Panel title="External IPv4 & Geolocation">
          <div className="col" style={{ gap: 0 }}>
            <div className="kv"><span className="kv-k">IP</span><span className="kv-v mono tiny">{netInfo.data?.ip ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Hostname</span><span className="kv-v mono tiny">{netInfo.data?.hostname ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">City</span><span className="kv-v mono tiny">{netInfo.data?.city ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Country</span><span className="kv-v mono tiny">{netInfo.data?.country ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Org/ASN</span><span className="kv-v mono tiny">{netInfo.data?.org ?? "—"}</span></div>
          </div>
        </Panel>

        <Panel title="DNSCrypt">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={status.dnscrypt ? "ok" : "warn"}>{status.dnscrypt ? "active" : "inactive"}</Badge>
            <Button size="sm" onClick={() => void toggle("dnscrypt")} disabled={busy === "dnscrypt"}>
              {busy === "dnscrypt" ? "…" : status.dnscrypt ? "Disable" : "Enable"}
            </Button>
          </div>
          <div className="mono tiny mute" style={{ marginTop: 8 }}>DNSCrypt resolver for encrypted DNS queries. Defaults on.</div>
        </Panel>

        <Panel title="VPN">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={status.vpn ? "ok" : "warn"}>{status.vpn ? "connected" : "disconnected"}</Badge>
            <Button size="sm" onClick={() => void toggle("vpn")} disabled={busy === "vpn"}>
              {busy === "vpn" ? "…" : status.vpn ? "Disconnect" : "Connect"}
            </Button>
          </div>
          <div className="mono tiny mute" style={{ marginTop: 8 }}>VPN tunnel for operator traffic. Defaults on.</div>
        </Panel>

        <Panel title="Proxy / Proxychains">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={status.proxy ? "ok" : "warn"}>proxy {status.proxy ? "on" : "off"}</Badge>
            <Button size="sm" onClick={() => void toggle("proxy")} disabled={busy === "proxy"}>
              {busy === "proxy" ? "…" : status.proxy ? "Disable" : "Enable"}
            </Button>
            <Badge tone={status.proxychains ? "ok" : "warn"}>proxychains {status.proxychains ? "on" : "off"}</Badge>
            <Button size="sm" onClick={() => void toggle("proxychains")} disabled={busy === "proxychains"}>
              {busy === "proxychains" ? "…" : status.proxychains ? "Disable" : "Enable"}
            </Button>
          </div>
          <div className="mono tiny mute" style={{ marginTop: 8 }}>HTTP/SOCKS proxy and proxychains for chained proxy routing.</div>
        </Panel>

        <Panel title="Socks5 Proxy">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={status.socks5 ? "ok" : "warn"}>{status.socks5 ? "listening" : "stopped"}</Badge>
            <Button size="sm" onClick={() => void toggle("socks5")} disabled={busy === "socks5"}>
              {busy === "socks5" ? "…" : status.socks5 ? "Stop" : "Start"}
            </Button>
          </div>
          <div className="mono tiny mute" style={{ marginTop: 8 }}>Local Socks5 proxy (default 127.0.0.1:9050).</div>
        </Panel>

        <Panel title="Tor">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={status.tor ? "ok" : "warn"}>{status.tor ? "running" : "stopped"}</Badge>
            <Button size="sm" onClick={() => void toggle("tor")} disabled={busy === "tor"}>
              {busy === "tor" ? "…" : status.tor ? "Stop" : "Start"}
            </Button>
          </div>
          <div className="mono tiny mute" style={{ marginTop: 8 }}>Tor daemon for anonymized traffic. Defaults off.</div>
        </Panel>

        <Panel title="No-IP.com DDNS">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={status.noip ? "ok" : "warn"}>{status.noip ? "synced" : "not configured"}</Badge>
            <Button size="sm" onClick={() => void toggle("noip")} disabled={busy === "noip"}>
              {busy === "noip" ? "…" : status.noip ? "Stop sync" : "Configure"}
            </Button>
          </div>
          <div className="mono tiny mute" style={{ marginTop: 8 }}>Built-in No-IP DDNS client for dynamic DNS updates.</div>
        </Panel>

        <Panel title="SSL / Certificates">
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <Badge tone={status.ssl ? "ok" : "warn"}>{status.ssl ? "valid" : "none"}</Badge>
            <Button size="sm" onClick={() => void toggle("ssl")} disabled={busy === "ssl"}>
              {busy === "ssl" ? "…" : status.ssl ? "Revoke" : "Generate"}
            </Button>
          </div>
          <div className="kv" style={{ marginTop: 8 }}><span className="kv-k">Cert type</span><span className="kv-v mono tiny">{status.cert}</span></div>
          <div className="mono tiny mute" style={{ marginTop: 4 }}>Self-signed / Let's Encrypt / custom. Certificate management for HTTPS endpoints.</div>
        </Panel>
      </div>

      <Panel title="Network queries">
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          {["dig", "nslookup", "traceroute", "whois", "ping", "curl"].map((q) => (
            <Button key={q} size="sm" variant="ghost" onClick={() => void runQuery(q)} disabled={busy === "query"}>
              {q}
            </Button>
          ))}
        </div>
        {result && <Terminal lines={[{ text: result, tone: "ok" }]} title="query result" maxHeight={160} />}
      </Panel>

      {result && !result.startsWith("error") && (
        <div className="mono tiny" style={{ marginTop: 8, color: "#66ff99" }}>{result}</div>
      )}
    </div>
  );
}
