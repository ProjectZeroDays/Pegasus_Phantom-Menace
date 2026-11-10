import { useState } from "react";
import { LifeBuoy, RefreshCw, Star } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";

interface Entry {
  id: string;
  title: string;
  summary: string;
  body: string;
  starred?: boolean;
}

export default function Help() {
  const help = useApi<{ entries: Entry[]; count: number }>("/help", { interval: 30000 });
  const reset = useApi<{ token: string | null; requested: boolean; delivery: string } | null>(
    null,
  );
  const [user, setUser] = useState("");
  const [issued, setIssued] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const entries = help.data?.entries ?? [];

  const requestReset = async () => {
    const res = await api.post<{ token: string | null; delivery: string }>(
      "/auth/password-reset/request",
      { user: user.trim() },
    );
    setIssued(res.token ? res.token : "no account matched that name");
  };

  return (
    <div className="page">
      <PageHeader title="Help" subtitle="Answers, troubleshooting and password recovery."
        actions={<Button size="sm" onClick={help.refresh}><RefreshCw size={12} /> Refresh</Button>} />
      <div className="stat-grid">
        <Stat value={entries.length} label="Articles" tone="info" />
        <Stat value={reset.data?.delivery ? "mail" : "token"} label="Reset delivery" tone="warn" />
      </div>

      <Panel title="Password reset">
        <div className="row" style={{ gap: 8 }}>
          <input
            className="select"
            style={{ flex: 1 }}
            value={user}
            onChange={(e) => setUser(e.target.value)}
            placeholder="operator name"
          />
          <Button size="sm" variant="primary" onClick={() => void requestReset()}>
            Issue reset token
          </Button>
        </div>
        {issued ? (
          <div className="mono tiny" style={{ marginTop: 8, wordBreak: "break-all" }}>
            {issued}
          </div>
        ) : null}
        <div className="tiny mute" style={{ marginTop: 6 }}>
          Tokens are single-use and expire after one hour.
        </div>
      </Panel>

      <Panel title="Help articles">
        {entries.length === 0 ? (
          <Empty icon={<LifeBuoy size={22} />} title="No help articles" />
        ) : (
          <div className="stack">
            {entries.map((entry) => (
              <div key={entry.id} className="vault-item">
                <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                  <div>
                    <div className="mono" style={{ fontSize: 12 }}>{entry.title}</div>
                    <div className="tiny mute">{entry.summary}</div>
                  </div>
                  <div className="row" style={{ gap: 6 }}>
                    {entry.starred ? <Badge tone="warn"><Star size={10} /> starred</Badge> : null}
                    <Button size="xs" onClick={() => void api.post("/stars", { key: `help:${entry.id}` }).then(help.refresh)}>
                      <Star size={11} />
                    </Button>
                    <Button size="xs" onClick={() => setOpen(open === entry.id ? null : entry.id)}>
                      {open === entry.id ? "Close" : "Read"}
                    </Button>
                  </div>
                </div>
                {open === entry.id ? <pre className="mono vault-open">{entry.body}</pre> : null}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
