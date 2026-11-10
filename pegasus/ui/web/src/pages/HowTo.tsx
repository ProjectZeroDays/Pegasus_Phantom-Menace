import { useState } from "react";
import { ListChecks, RefreshCw, Star } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";

interface Entry {
  id: string;
  title: string;
  summary: string;
  body: string;
  starred?: boolean;
}

export default function HowTo() {
  const howto = useApi<{ entries: Entry[]; count: number }>("/howto", { interval: 30000 });
  const [open, setOpen] = useState<string | null>(null);
  const entries = howto.data?.entries ?? [];

  return (
    <div className="page">
      <PageHeader title="How-To" subtitle="Step by step runbooks for common tasks."
        actions={<Button size="sm" onClick={howto.refresh}><RefreshCw size={12} /> Refresh</Button>} />
      <div className="stat-grid">
        <Stat value={entries.length} label="Runbooks" tone="info" />
        <Stat value={entries.filter((e) => e.starred).length} label="Starred" tone="warn" />
      </div>
      <Panel title="Runbooks">
        {entries.length === 0 ? (
          <Empty icon={<ListChecks size={22} />} title="No runbooks yet" />
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
                    <Button size="xs" onClick={() => void api.post("/stars", { key: `howto:${entry.id}` }).then(howto.refresh)}>
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
