import { useState } from "react";
import { KeyRound, RefreshCw, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { Badge, Button, Field, PageHeader, Panel, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";

export default function Wordlists() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    surname: "",
    nickname: "",
    team: "",
    date: "",
    keywords: "",
    min_length: 6,
    max_length: 16,
    leet: true,
    append_numbers: true,
    output: "",
  });

  const generate = async () => {
    const data = await api.post<{ job: Job }>("/passgen", form);
    setJobId(data.job.id);
  };

  const runWizard = async () => {
    const data = await api.post<{ job: Job }>("/commands/passgen/run", { args: [] });
    setJobId(data.job.id);
  };

  return (
    <div className="page">
      <PageHeader
        title="Wordlists"
        subtitle="Profile-driven wordlist generation with mutation rules"
        actions={
          <>
            <Button size="sm" onClick={() => void runWizard()}>
              <Sparkles size={12} /> Guided wizard
            </Button>
            <Button size="sm" variant="primary" onClick={() => void generate()}>
              <KeyRound size={12} /> Generate
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value="4" label="Seed dimensions" hint="name · surname · nickname · team" tone="info" />
        <Stat value={form.leet ? "ON" : "OFF"} label="Leet substitution" tone={form.leet ? "ok" : undefined} />
        <Stat value={`${form.min_length}–${form.max_length}`} label="Length window" />
        <Stat value={form.append_numbers ? "ON" : "OFF"} label="Numeric suffixes" />
      </div>

      <Panel title="Seed profile">
        <div className="form-row">
          <Field label="First name">
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Alex" />
          </Field>
          <Field label="Surname">
            <input className="input" value={form.surname} onChange={(e) => setForm({ ...form, surname: e.target.value })} placeholder="Warner" />
          </Field>
          <Field label="Nickname">
            <input className="input" value={form.nickname} onChange={(e) => setForm({ ...form, nickname: e.target.value })} placeholder="lex" />
          </Field>
          <Field label="Team / company">
            <input className="input" value={form.team} onChange={(e) => setForm({ ...form, team: e.target.value })} placeholder="RedTeam" />
          </Field>
          <Field label="Date (YYYY)">
            <input className="input" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} placeholder="1994" />
          </Field>
          <Field label="Extra keywords (comma separated)">
            <input className="input" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} placeholder="pet, city, band" />
          </Field>
          <Field label="Min length">
            <input className="input" type="number" value={form.min_length} onChange={(e) => setForm({ ...form, min_length: Number(e.target.value) })} />
          </Field>
          <Field label="Max length">
            <input className="input" type="number" value={form.max_length} onChange={(e) => setForm({ ...form, max_length: Number(e.target.value) })} />
          </Field>
          <Field label="Output file">
            <input className="input" value={form.output} onChange={(e) => setForm({ ...form, output: e.target.value })} placeholder="wordlist.txt" />
          </Field>
        </div>
        <div className="row wrap" style={{ marginTop: 12, gap: 16 }}>
          <label className="check">
            <input type="checkbox" checked={form.leet} onChange={(e) => setForm({ ...form, leet: e.target.checked })} />
            leet substitutions (a→4, e→3, …)
          </label>
          <label className="check">
            <input type="checkbox" checked={form.append_numbers} onChange={(e) => setForm({ ...form, append_numbers: e.target.checked })} />
            append numeric suffixes
          </label>
          <span className="spacer" />
          <Badge tone="dim">writes to workspace/payloads</Badge>
        </div>
      </Panel>

      {jobId && (
        <Panel title="Generation output">
          <JobOutput jobId={jobId} title="wordlist" height={320} />
        </Panel>
      )}
    </div>
  );
}
