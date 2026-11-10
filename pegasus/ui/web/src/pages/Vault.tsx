import { useState } from "react";
import { Archive, Eye, Lock, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, Input, PageHeader, Panel, Stat, Textarea } from "@/components/ui";

interface VaultItem {
  id: string;
  name: string;
  kind: string;
  tags: string[];
  bytes: number;
  cipher: string;
  created: number;
}

export default function Vault() {
  const status = useApi<{ items: number; cipher: string; master_key_present: boolean; directory: string }>(
    "/vault/status",
    { interval: 20000 },
  );
  const items = useApi<{ items: VaultItem[] }>("/vault/items", { interval: 20000 });
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [kind, setKind] = useState("artifact");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [opened, setOpened] = useState<Record<string, string>>({});

  const store = async () => {
    if (!name.trim() || !content) {
      setMsg("name and content are required");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/vault/items", { name: name.trim(), content, kind });
      setName("");
      setContent("");
      items.refresh();
      status.refresh();
      setMsg("sealed into the vault");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "could not seal item");
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    try {
      const res = await api.get<{ item: VaultItem; content: string }>(`/vault/items/${id}`);
      setOpened((prev) => ({ ...prev, [id]: res.content }));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "could not open item");
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Delete this vault item? This cannot be undone.")) return;
    await api.del(`/vault/items/${id}`);
    items.refresh();
    status.refresh();
  };

  return (
    <div className="page">
      <PageHeader
        title="Encrypted Vault"
        subtitle="Sealed loot store. Items are encrypted on disk with a local master key."
        actions={<Button size="sm" onClick={() => { items.refresh(); status.refresh(); }}>
          <RefreshCw size={12} /> Refresh
        </Button>}
      />

      <div className="stat-grid">
        <Stat value={status.data?.items ?? 0} label="Items" tone="info" />
        <Stat value={status.data?.cipher ?? "—"} label="Cipher" tone="ok" />
        <Stat value={status.data?.master_key_present ? "present" : "pending"} label="Master key" tone="warn" />
      </div>

      <Panel title="Seal an artefact" actions={<Badge tone="dim"><Lock size={10} /> encrypted</Badge>}>
        <Field label="Name">
          <Input value={name} onChange={setName} placeholder="evidence bundle" />
        </Field>
        <div style={{ marginTop: 8 }}>
          <Field label="Content">
            <Textarea value={content} onChange={setContent} rows={4} placeholder="text to seal" />
          </Field>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 10 }}>
          <Button variant="primary" onClick={() => void store()} disabled={busy}>
            <Plus size={13} /> {busy ? "sealing…" : "Seal"}
          </Button>
          {msg ? <span className="mono tiny">{msg}</span> : null}
        </div>
      </Panel>

      <Panel title="Vault contents">
        {(items.data?.items ?? []).length === 0 ? (
          <Empty icon={<Archive size={22} />} title="The vault is empty"
            detail="Seal an artefact above to store it." />
        ) : (
          <div className="stack">
            {(items.data?.items ?? []).map((item) => (
              <div key={item.id} className="vault-item">
                <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                  <div>
                    <div className="mono" style={{ fontSize: 12 }}>{item.name}</div>
                    <div className="tiny mute">
                      {item.kind} &middot; {item.bytes} bytes &middot; {item.cipher}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 6 }}>
                    <Button size="xs" onClick={() => void open(item.id)}>
                      <Eye size={11} /> Open
                    </Button>
                    <Button size="xs" variant="danger" onClick={() => void remove(item.id)}>
                      <Trash2 size={11} />
                    </Button>
                  </div>
                </div>
                {opened[item.id] ? (
                  <pre className="mono vault-open">{opened[item.id]}</pre>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
