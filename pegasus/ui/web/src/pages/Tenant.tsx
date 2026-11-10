import { useState } from "react";
import { Building2, Plus, RefreshCw, Users, UsersRound } from "lucide-react";
import { api, useApi, ApiError } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";

interface Org {
  id: number | string;
  name: string;
  role: string;
}

export default function Tenant() {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const orgs = useApi<{ orgs: Org[] }>("/tenants", { interval: 60000 });

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.post("/tenants", { name: name.trim() });
      setName("");
      orgs.refresh();
    } finally {
      setBusy(false);
    }
  };

  const rows = orgs.data?.orgs ?? [];
  const forbidden = orgs.error instanceof ApiError && (orgs.error.status === 401 || orgs.error.status === 403 || orgs.error.status === 428);

  return (
    <div className="page">
      <PageHeader
        title="Multi-Tenant Architecture"
        subtitle="Organization-scoped tenancy with isolated workspaces, RBAC, and usage accounting"
        actions={<Button size="sm" onClick={orgs.refresh}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={rows.length} label="Memberships" tone="info" />
        <Stat value={rows.filter((o) => o.role === "owner" || o.role === "admin").length} label="Admin/Owner roles" tone="ok" />
        <Stat value={rows.filter((o) => o.role === "viewer").length} label="Viewer roles" tone="info" />
        <Stat value={forbidden ? "auth required" : "connected"} label="Directory status" tone={forbidden ? "warn" : "ok"} />
      </div>

      <Panel title="Create organization">
        <div className="form-row">
          <Field label="Organization name">
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Red Team LLC" />
          </Field>
          <Field label="Create">
            <button className="btn btn-primary" onClick={() => void create()} disabled={busy || !name.trim()}>
              <Plus size={13} /> Create tenant
            </button>
          </Field>
        </div>
        <p className="tiny mute">New tenants are created under your operator identity with admin role. Scoping rules, quotas, and per-tenant secrets live under <code>tenant_routes</code> (RBAC: admin gate on writes).</p>
      </Panel>

      <Panel title="Your organizations" tight>
        {orgs.error ? (
          <Empty
            icon={<UsersRound size={16} />}
            title={forbidden ? "Operator sign-in required" : "Directory unavailable"}
            detail={forbidden ? "Tenant listing requires an authenticated operator session (401/403/428). Sign in via the setup flow or configure PEGASUS_REQUIRE_AUTH + an API token." : String(orgs.error)}
            action={<Button size="sm" onClick={orgs.refresh}>Retry</Button>}
          />
        ) : rows.length === 0 ? (
          <Empty icon={<Building2 size={16} />} title="No tenants yet" detail="Create your first organization above." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Organization</th><th>ID</th><th>Your role</th></tr></thead>
              <tbody>
                {rows.map((org) => (
                  <tr key={String(org.id)}>
                    <td className="td-strong"><Building2 size={11} style={{ display: "inline" }} /> {org.name}</td>
                    <td className="mono tiny">{org.id}</td>
                    <td>
                      <Badge tone={org.role === "admin" || org.role === "owner" ? "primary" : org.role === "editor" ? "info" : "dim"}>
                        {org.role}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Capabilities by tenant" tight>
        <ul className="tiny" style={{ margin: 0, paddingLeft: 18 }}>
          <li>Isolated data store per tenant (scopes under <code>pegasus/modules/tenant</code>)</li>
          <li>RBAC: owner / admin / editor / viewer roles</li>
          <li>Usage accounting per tenant (token ledger quota alignment)</li>
          <li>Tenant-scoped secrets, quotas, and audit trails</li>
          <li><Users size={11} style={{ display: "inline" }} /> Member invitations and role management via CLI: <code>tenant list / create / grant</code></li>
        </ul>
      </Panel>
    </div>
  );
}
