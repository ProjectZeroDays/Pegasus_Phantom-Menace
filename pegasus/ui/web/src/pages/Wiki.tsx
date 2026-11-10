import { useState } from "react";
import { BookOpen, RefreshCw, Star } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";

interface Entry {
  id: string;
  title: string;
  summary: string;
  body: string;
  section: string;
  starred?: boolean;
}

export default function Wiki() {
  const wiki = useApi<{ entries: Entry[]; count: number }>("/wiki", { interval: 30000 });
  const [open, setOpen] = useState<string | null>(null);
  const entries = wiki.data?.entries ?? [];

  const toggleStar = async (id: string) => {
    await api.post("/stars", { key: `wiki:${id}` });
    wiki.refresh();
  };

  return (
    <div className="page">
      <PageHeader title="Wiki" subtitle="Operating knowledge for the platform."
        actions={<Button size="sm" onClick={wiki.refresh}><RefreshCw size={12} /> Refresh</Button>} />
      <div className="stat-grid">
        <Stat value={entries.length} label="Articles" tone="info" />
        <Stat value={entries.filter((e) => e.starred).length} label="Starred" tone="warn" />
      </div>
      <Panel title="Articles">
        {entries.length === 0 ? (
          <Empty icon={<BookOpen size={22} />} title="No articles yet"
            detail="Wiki content ships with the console content directory." />
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
                    <Button size="xs" onClick={() => void toggleStar(entry.id)}>
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
