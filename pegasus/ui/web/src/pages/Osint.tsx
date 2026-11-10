import { useState } from "react";
import { Download, KeyRound, Radar, RefreshCw, Search, Star, Wrench } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, Input, PageHeader, Panel, Select, Stat, Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

interface Service {
  id: string;
  name: string;
  category: string;
  category_label: string;
  url: string;
  kind: "api" | "tool";
  key_env: string | null;
  key_required: boolean;
  key_configured: boolean;
  key_source: string;
  notes: string;
}

interface Tool {
  id: string;
  name: string;
  kind: string;
  installed: boolean;
  path: string;
  version: string | null;
  detail: string;
  license: string | null;
  notes: string;
}

interface Result {
  [key: string]: unknown;
}

export default function Osint() {
  const catalog = useApi<{ categories: { id: string; label: string }[]; services: Service[]; count: number }>(
    "/osint/catalog",
    { interval: 60000 },
  );
  const tools = useApi<{ tools: Tool[]; tools_dir: string }>("/osint/tools", { interval: 60000 });
  const [category, setCategory] = useState("all");
  const [service, setService] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[] | null>(null);
  const [meta, setMeta] = useState<{ service?: string; name?: string; count?: number; elapsed?: number; needs_key?: boolean; error?: string; manual_url?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [keyFor, setKeyFor] = useState<string | null>(null);
  const [keyValue, setKeyValue] = useState("");

  const services = catalog.data?.services ?? [];
  const categories = catalog.data?.categories ?? [];
  const visible = category === "all" ? services : services.filter((s) => s.category === category);
  const apiServices = visible.filter((s) => s.kind === "api");
  const toolServices = visible.filter((s) => s.kind === "tool");

  const runSearch = async () => {
    if (!service || !query.trim()) {
      setMsg("pick a service and enter a query");
      return;
    }
    setBusy(true);
    setMsg(null);
    setResults(null);
    try {
      const res = await api.post<{
        results?: Result[];
        count?: number;
        name?: string;
        elapsed?: number;
        needs_key?: boolean;
        error?: string;
        manual_url?: string;
      }>("/osint/search", { service, query: query.trim() });
      setResults(res.results ?? []);
      setMeta(res);
      if (res.needs_key) {
        setMsg("this service needs an API key - add one below, or open the manual search URL");
      }
    } catch (e) {
      setMeta({ error: e instanceof ApiError ? e.message : "search failed" });
      setMsg(e instanceof ApiError ? e.message : "search failed");
    } finally {
      setBusy(false);
    }
  };

  const saveKey = async () => {
    if (!keyFor) return;
    try {
      await api.post("/osint/keys", { service: keyFor, key: keyValue.trim() });
      setKeyFor(null);
      setKeyValue("");
      catalog.refresh();
      setMsg("key stored");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "could not store the key");
    }
  };

  const clearKey = async (id: string) => {
    await api.del(`/osint/keys/${id}`);
    catalog.refresh();
  };

  const installTool = async (id: string) => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.post<{ needs_confirm?: boolean; plan?: { license?: string } }>(
        `/osint/tools/${id}/install`,
        {},
      );
      if (res.needs_confirm) {
        const licence = res.plan?.license ?? "";
        if (!window.confirm(`Install ${id}?${licence ? "\n\n" + licence : ""}`)) {
          setBusy(false);
          return;
        }
        await api.post(`/osint/tools/${id}/install`, { confirm: true });
      }
      tools.refresh();
      setMsg(`${id} install finished`);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "install failed");
    } finally {
      setBusy(false);
    }
  };

  const openService = (s: Service) => {
    setService(s.id);
    setCategory(s.category);
  };

  return (
    <div className="page">
      <PageHeader
        title="OSINT Search Engines"
        subtitle="Code, attack-surface, threat-intelligence, server and WiFi sources. Passive queries only."
        actions={<Button size="sm" onClick={() => { catalog.refresh(); tools.refresh(); }}>
          <RefreshCw size={12} /> Refresh
        </Button>}
      />

      <div className="stat-grid">
        <Stat value={services.length} label="Sources" tone="info" />
        <Stat value={services.filter((s) => s.key_configured).length} label="Keyed" tone="ok" />
        <Stat value={(tools.data?.tools ?? []).filter((t) => t.installed).length} label="Tools" tone="warn" />
      </div>

      <Panel title="Query" actions={<Badge tone="dim">passive</Badge>}>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Select value={category} onChange={setCategory}>
            <option value="all">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </Select>
          <Select value={service} onChange={setService}>
            <option value="">-- pick a source --</option>
            {apiServices.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}{s.key_required && !s.key_configured ? " (needs key)" : ""}
              </option>
            ))}
          </Select>
          <Input value={query} onChange={setQuery} placeholder="host, domain, IP, hash, email" />
          <Button variant="primary" onClick={() => void runSearch()} disabled={busy}>
            <Search size={13} /> {busy ? "searching…" : "Search"}
          </Button>
        </div>
        {msg ? <div className="mono tiny" style={{ marginTop: 8 }}>{msg}</div> : null}
        {meta?.manual_url ? (
          <div className="mono tiny" style={{ marginTop: 6 }}>
            <a href={meta.manual_url} target="_blank" rel="noreferrer">open the manual search</a>
          </div>
        ) : null}
      </Panel>

      {results !== null ? (
        <Panel
          title={`Results${meta?.name ? ` · ${meta.name}` : ""}`}
          actions={<Badge tone="dim">{meta?.count ?? results.length} hits · {meta?.elapsed ?? 0}s</Badge>}
        >
          {results.length === 0 ? (
            <Empty icon={<Radar size={22} />} title="No results" detail="Try a broader query." />
          ) : (
            <Table>
              <Thead>
                <Tr>
                  {Object.keys(results[0]).slice(0, 6).map((k) => <Th key={k}>{k}</Th>)}
                </Tr>
              </Thead>
              <Tbody>
                {results.map((row, i) => (
                  <Tr key={i}>
                    {Object.keys(results[0]).slice(0, 6).map((k) => (
                      <Td key={k} className="mono" style={{ fontSize: 11 }}>
                        {String(row[k] ?? "")}
                      </Td>
                    ))}
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </Panel>
      ) : null}

      <Panel title="Sources">
        <div className="stack">
          {visible.map((s) => (
            <div key={s.id} className="vault-item">
              <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                <div>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="mono" style={{ fontSize: 12 }}>{s.name}</span>
                    <Badge tone="dim">{s.category_label}</Badge>
                    {s.key_required ? (
                      <Badge tone={s.key_configured ? "ok" : "warn"}>
                        {s.key_configured ? "key set" : "key needed"}
                      </Badge>
                    ) : (
                      <Badge tone="ok">no key</Badge>
                    )}
                  </div>
                  <div className="tiny mute">{s.notes}</div>
                </div>
                <div className="row" style={{ gap: 6 }}>
                  {s.kind === "api" ? (
                    <>
                      <Button size="xs" onClick={() => openService(s)}>
                        <Search size={11} /> Use
                      </Button>
                      {s.key_env ? (
                        <Button size="xs" onClick={() => { setKeyFor(s.id); setKeyValue(""); }}>
                          <KeyRound size={11} />
                        </Button>
                      ) : null}
                      <a href={s.url} target="_blank" rel="noreferrer" className="mono tiny">
                        <Star size={11} />
                      </a>
                    </>
                  ) : (
                    <Button size="xs" onClick={() => void installTool(s.id)} disabled={busy}>
                      <Download size={11} /> Install
                    </Button>
                  )}
                </div>
              </div>
              {keyFor === s.id ? (
                <div className="row" style={{ gap: 8, marginTop: 8 }}>
                  <Input value={keyValue} onChange={setKeyValue} placeholder={s.key_env ?? "api key"} />
                  <Button size="xs" variant="primary" onClick={() => void saveKey()}>Store</Button>
                  <Button size="xs" variant="danger" onClick={() => { void clearKey(s.id); setKeyFor(null); }}>
                    Clear
                  </Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Local tooling" actions={<Badge tone="dim">{tools.data?.tools_dir ?? "~/.pegasus/tools"}</Badge>}>
        {(tools.data?.tools ?? []).length === 0 ? (
          <Empty icon={<Wrench size={22} />} title="No tools registered" />
        ) : (
          <div className="stack">
            {(tools.data?.tools ?? []).map((t) => (
              <div key={t.id} className="vault-item">
                <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                  <div>
                    <div className="row" style={{ gap: 8 }}>
                      <span className="mono" style={{ fontSize: 12 }}>{t.name}</span>
                      <Badge tone={t.installed ? "ok" : "dim"}>
                        {t.installed ? "installed" : "not installed"}
                      </Badge>
                      {t.version ? <Badge tone="dim">v{t.version}</Badge> : null}
                    </div>
                    <div className="tiny mute">{t.notes}</div>
                    {t.license ? <div className="tiny mute">licence: {t.license}</div> : null}
                  </div>
                  <Button size="xs" onClick={() => void installTool(t.id)} disabled={busy}>
                    <Download size={11} /> {t.installed ? "Reinstall" : "Install"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
