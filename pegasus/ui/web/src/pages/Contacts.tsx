import { useMemo, useState } from "react";
import { Mail, Phone, RefreshCw, Search, Users } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { ContactRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Stat } from "@/components/ui";
import { initials } from "@/lib/format";

export default function Contacts() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{ rows: ContactRow[] }>("contacts", 60000);
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const list = data?.rows ?? [];
    if (!query.trim()) return list;
    const needle = query.toLowerCase();
    return list.filter(
      (row) =>
        row.name.toLowerCase().includes(needle) ||
        row.phones.some((phone) => phone.toLowerCase().includes(needle)) ||
        row.emails.some((email) => email.toLowerCase().includes(needle)),
    );
  }, [data, query]);

  const totalPhones = (data?.rows ?? []).reduce((acc, row) => acc + row.phones.length, 0);

  return (
    <div className="page">
      <PageHeader
        title="Contacts"
        subtitle="Address book extracted from the contacts provider"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <Users size={12} /> Pull from device
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={data?.rows.length ?? "—"} label="Contacts" tone="info" />
        <Stat value={totalPhones} label="Phone numbers" />
        <Stat value={rows.length} label="Visible after filter" />
        <Stat value={serial ? "BOUND" : "IDLE"} label="Device" hint={serial ?? "none"} />
      </div>

      <Panel
        title="Address book"
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 220 }} placeholder="filter name, phone, email" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      >
        {!serial ? (
          <Empty icon={<Users size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <Loading label="Reading contacts provider…" rows={5} />
        ) : rows.length === 0 ? (
          <Empty icon={<Users size={16} />} title="No contacts cached" detail="Pull from device to read the address book." action={<Button size="sm" variant="primary" onClick={() => void collect()}>Collect now</Button>} />
        ) : (
          <div className="grid-3">
            {rows.map((row) => (
              <div className="cmd-card" key={row.id} style={{ cursor: "default" }}>
                <div className="row" style={{ gap: 10 }}>
                  <div className="avatar">{initials(row.name)}</div>
                  <div style={{ minWidth: 0 }}>
                    <div className="td-strong td-truncate">{row.name}</div>
                    <div className="tiny mute">{row.phones.length} number(s)</div>
                  </div>
                </div>
                <div className="col" style={{ gap: 4 }}>
                  {row.phones.slice(0, 3).map((phone) => (
                    <div className="row tiny mono" key={phone} style={{ gap: 6 }}>
                      <Phone size={10} className="mute" /> {phone}
                    </div>
                  ))}
                  {row.emails.slice(0, 2).map((email) => (
                    <div className="row tiny mono" key={email} style={{ gap: 6 }}>
                      <Mail size={10} className="mute" /> <span className="td-truncate">{email}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
