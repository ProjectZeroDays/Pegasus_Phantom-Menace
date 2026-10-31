import { useMemo, useState } from "react";
import { Search, Sparkles, Zap } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Job } from "@/lib/types";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";

interface LiveSkill {
  id: string;
  name: string;
  file: string;
  version: string;
  description: string;
  category: string;
  trigger: string;
  commands: number;
  author: string;
}

interface Family {
  id: string;
  label: string;
  description: string;
  commands: string[];
  zeroClickFamilies: string[];
}

export default function Skills() {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<string>("all");
  const [jobId, setJobId] = useState<string | null>(null);

  const live = useApi<{ skills: LiveSkill[]; count: number }>("/skills", { interval: 60000 });
  const families = useApi<{ families: Family[]; count: number }>("/agents/families", { interval: 60000 });

  const groups = useMemo(
    () => ["all", ...Array.from(new Set((live.data?.skills ?? []).map((s) => s.category))).sort()],
    [live.data],
  );

  const skills = useMemo(() => {
    let list = live.data?.skills ?? [];
    if (group !== "all") list = list.filter((skill) => skill.category === group);
    if (query.trim()) {
      const needle = query.toLowerCase();
      list = list.filter(
        (skill) =>
          skill.name.toLowerCase().includes(needle) ||
          skill.description.toLowerCase().includes(needle) ||
          skill.trigger.toLowerCase().includes(needle),
      );
    }
    return list;
  }, [group, query, live.data]);

  const dispatch = async (command: string) => {
    const data = await api.post<{ job: Job }>(`/commands/${command}/run`, { args: [] });
    setJobId(data.job.id);
  };

  return (
    <div className="page">
      <PageHeader
        title="Skills Catalog"
        subtitle="Agent skill packs available to the autonomous pipeline"
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 240 }} placeholder="search skill or command" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      />

      <div className="stat-grid">
        <Stat value={live.data?.count ?? "—"} label="Skill packs" tone="info" hint="live from .openfable-skills" />
        <Stat value={families.data?.count ?? "—"} label="Agent families" hint="Android, IoT, Windows, Linux, macOS, C2, payload, exploitation" />
        <Stat value={skills.length} label="Visible after filter" />
        <Stat value={new Set((families.data?.families ?? []).flatMap((f) => f.commands)).size} label="Linked commands" />
      </div>

      {(families.data?.families ?? []).length > 0 && (
        <Panel title="Agent families" actions={<Badge tone="dim">{families.data?.count} domains</Badge>}>
          <div className="grid-3">
            {(families.data?.families ?? []).map((f) => (
              <div className="cmd-card" key={f.id} style={{ cursor: "default" }}>
                <div className="cmd-name">
                  <span className="row" style={{ gap: 7 }}><Sparkles size={12} />{f.label}</span>
                  <Badge tone="primary">{f.id}</Badge>
                </div>
                <div className="cmd-desc">{f.description}</div>
                <div className="tag-row">
                  {f.commands.map((c) => <span className="tag" key={c}>{c}</span>)}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel
        title="Skill domains"
        actions={
          <div className="seg">
            {groups.map((item) => (
              <button
                key={item}
                className={item === group ? "seg-btn active" : "seg-btn"}
                onClick={() => setGroup(item)}
              >
                {item === "all" ? "All" : item}
              </button>
            ))}
          </div>
        }
      >
        {skills.length === 0 ? (
          <Empty icon={<Sparkles size={16} />} title="No skills match" detail="Adjust the search or domain filter." />
        ) : (
          <div className="grid-3">
            {skills.map((skill) => (
              <div className="cmd-card" key={skill.id} style={{ cursor: "default" }}>
                <div className="cmd-name">
                  <span className="row" style={{ gap: 7 }}><Zap size={12} />{skill.name}</span>
                  <Badge tone="primary">{skill.category}</Badge>
                </div>
                <div className="cmd-desc">{skill.description}</div>
                <div className="tag-row">
                  {skill.trigger && <span className="tag">trigger: {skill.trigger}</span>}
                  {skill.author && <span className="tag">{skill.author}</span>}
                </div>
                <div className="row">
                  <Button size="xs" variant="primary" onClick={() => void dispatch(skill.trigger || skill.id)}>
                    invoke
                  </Button>
                  <span className="tiny mute mono">v{skill.version || "1.0"} · {skill.commands} cmds</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {jobId && (
        <Panel title="Skill invocation">
          <JobOutput jobId={jobId} title="skill" height={300} />
        </Panel>
      )}
    </div>
  );
}
