import { useState } from "react";
import { Fingerprint, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, Input, PageHeader, Panel, Stat, Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

interface Entry {
  id: string;
  title: string;
  severity: string;
  cvss: number;
  products: string[];
  keywords: string[];
  affected_versions: string[];
  fixed_in: string;
  reference: string;
  remediation: string;
}

interface Validator {
  id: string;
  name: string;
  description: string;
  platform: string;
}

interface Finding {
  check: string;
  state?: string;
  risk?: string;
  detail?: string;
  error?: string;
}

export default function CveFramework() {
  const catalogue = useApi<{ entries: Entry[]; count: number }>("/cve/catalogue", { interval: 60000 });
  const validators = useApi<{ validators: Validator[] }>("/cve/validators", { interval: 60000 });
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Entry[] | null>(null);
  const [assets, setAssets] = useState("Apache Log4j2\n2.14.1");
  const [matches, setMatches] = useState<{ product: string; version: string; count: number }[]>([]);
  const [findings, setFindings] = useState<Record<string, Finding[]>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const entries = results ?? catalogue.data?.entries ?? [];

  const search = async () => {
    const res = await api.get<{ entries: Entry[] }>(`/cve/search?q=${encodeURIComponent(query)}`);
    setResults(res.entries);
  };

  const fingerprint = async () => {
    const parsed = assets.split(/\n+/).map((line) => line.trim()).filter(Boolean);
    const list: { product: string; version: string }[] = [];
    for (let i = 0; i < parsed.length; i += 2) {
      list.push({ product: parsed[i], version: parsed[i + 1] ?? "" });
    }
    try {
      const res = await api.post<{ results: { product: string; version: string; count: number }[] }>(
        "/cve/fingerprint",
        { assets: list },
      );
      setMatches(res.results);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "fingerprint failed");
    }
  };

  const runValidator = async (id: string) => {
    try {
      const res = await api.post<{ findings: Finding[] }>(`/cve/validators/${id}/run`);
      setFindings((prev) => ({ ...prev, [id]: res.findings }));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "validator failed");
    }
  };

  return (
    <div className="page">
      <PageHeader title="CVE Framework" subtitle="Catalogue, fingerprinting and passive posture validation."
        actions={<Button size="sm" onClick={catalogue.refresh}><RefreshCw size={12} /> Refresh</Button>} />

      <div className="stat-grid">
        <Stat value={catalogue.data?.count ?? 0} label="Catalogue" tone="info" />
        <Stat value={(validators.data?.validators ?? []).length} label="Validators" tone="ok" />
        <Stat value={matches.reduce((n, m) => n + m.count, 0)} label="Matches" tone="warn" />
      </div>

      <Panel title="Search the catalogue">
        <div className="row" style={{ gap: 8 }}>
          <Input value={query} onChange={setQuery} placeholder="log4j, smb, bluekeep…" />
          <Button size="sm" onClick={() => void search()}>
            <Search size={12} /> Search
          </Button>
        </div>
        <div style={{ marginTop: 12 }}>
          {entries.length === 0 ? (
            <Empty icon={<ShieldAlert size={22} />} title="No entries" />
          ) : (
            <Table>
              <Thead><Tr><Th>CVE</Th><Th>Severity</Th><Th>Title</Th><Th>Fixed in</Th></Tr></Thead>
              <Tbody>
                {entries.map((e) => (
                  <Tr key={e.id}>
                    <Td className="mono">{e.id}</Td>
                    <Td>
                      <Badge tone={e.severity === "critical" ? "err" : e.severity === "high" ? "warn" : "dim"}>
                        {e.severity}
                      </Badge>
                    </Td>
                    <Td>{e.title}</Td>
                    <Td className="mono">{e.fixed_in}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </div>
      </Panel>

      <Panel title="Fingerprint an inventory">
        <Field label="Product and version, one per pair of lines">
          <textarea
            className="select mono"
            style={{ width: "100%", minHeight: 90 }}
            value={assets}
            onChange={(e) => setAssets(e.target.value)}
          />
        </Field>
        <div className="row" style={{ gap: 8, marginTop: 10 }}>
          <Button variant="primary" onClick={() => void fingerprint()}>
            <Fingerprint size={13} /> Fingerprint
          </Button>
          {msg ? <span className="mono tiny">{msg}</span> : null}
        </div>
        {matches.length ? (
          <div className="stack" style={{ marginTop: 10 }}>
            {matches.map((m, i) => (
              <div key={i} className="row tiny" style={{ gap: 8 }}>
                <span className="mono">{m.product} {m.version}</span>
                <Badge tone={m.count ? "err" : "ok"}>{m.count} match</Badge>
              </div>
            ))}
          </div>
        ) : null}
      </Panel>

      <Panel title="Passive validators" actions={<Badge tone="dim">read-only</Badge>}>
        <div className="stack">
          {(validators.data?.validators ?? []).map((v) => (
            <div key={v.id} className="vault-item">
              <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                <div>
                  <div className="mono" style={{ fontSize: 12 }}>{v.name}</div>
                  <div className="tiny mute">{v.description}</div>
                </div>
                <Button size="xs" onClick={() => void runValidator(v.id)}>Run</Button>
              </div>
              {findings[v.id] ? (
                <div className="stack" style={{ marginTop: 6 }}>
                  {findings[v.id].map((f, i) => (
                    <div key={i} className="row tiny" style={{ gap: 8 }}>
                      <span className="mono">{f.check}</span>
                      <span>{f.state ?? f.error ?? ""}</span>
                      {f.risk ? <Badge tone={f.risk === "high" ? "err" : f.risk === "medium" ? "warn" : "ok"}>{f.risk}</Badge> : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
