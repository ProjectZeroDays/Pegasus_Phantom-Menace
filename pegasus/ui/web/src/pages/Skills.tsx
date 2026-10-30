import { useMemo, useState } from "react";
import { Search, Sparkles, Zap } from "lucide-react";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { SKILL_CATALOG } from "@/nav";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";

export default function Skills() {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<string>("all");
  const [jobId, setJobId] = useState<string | null>(null);

  const groups = useMemo(
    () => ["all", ...Array.from(new Set(SKILL_CATALOG.map((skill) => skill.group))).sort()],
    [],
  );

  const skills = useMemo(() => {
    let list = SKILL_CATALOG;
    if (group !== "all") list = list.filter((skill) => skill.group === group);
    if (query.trim()) {
      const needle = query.toLowerCase();
      list = list.filter(
        (skill) =>
          skill.name.toLowerCase().includes(needle) ||
          skill.description.toLowerCase().includes(needle) ||
          skill.commands.some((command) => command.includes(needle)),
      );
    }
    return list;
  }, [group, query]);

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
        <Stat value={SKILL_CATALOG.length} label="Skill packs" tone="info" />
        <Stat value={groups.length - 1} label="Domains" />
        <Stat value={new Set(SKILL_CATALOG.flatMap((skill) => skill.commands)).size} label="Linked commands" />
        <Stat value={skills.length} label="Visible after filter" />
      </div>

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
                  <Badge tone="primary">{skill.group}</Badge>
                </div>
                <div className="cmd-desc">{skill.description}</div>
                <div className="tag-row">
                  {skill.commands.map((command) => <span className="tag" key={command}>{command}</span>)}
                </div>
                <div className="row">
                  <Button size="xs" variant="primary" onClick={() => void dispatch(skill.commands[0])}>
                    invoke
                  </Button>
                  <span className="tiny mute mono">/skill load {skill.id}</span>
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
