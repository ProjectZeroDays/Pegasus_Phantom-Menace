import { useState } from "react";
import { KeyRound, Plus, RefreshCw, Trash2, Users, ShieldCheck, Shield } from "lucide-react";
import { api, useApi, ApiError } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";

interface AdminUser {
  id: number;
  user: string;
  role: string;
  created: number;
}

export default function AdminUsers() {
  const list = useApi<{ users: AdminUser[] }>("/admin/users", { interval: 30000 });
  const [form, setForm] = useState({ user: "", password: "", role: "operator" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [resetId, setResetId] = useState<number | null>(null);
  const [resetPw, setResetPw] = useState("");

  const users = list.data?.users ?? [];
  const forbidden = list.error instanceof ApiError && (list.error.status === 401 || list.error.status === 403);

  const create = async () => {
    if (!form.user.trim() || !form.password) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/admin/users", { user: form.user.trim(), password: form.password, role: form.role });
      setForm({ user: "", password: "", role: "operator" });
      list.refresh();
      setMsg("operator created");
    } catch (e) {
      setMsg(e instanceof ApiError ? `error: ${e.message}` : "create failed");
    } finally {
      setBusy(false);
    }
  };

  const changeRole = async (id: number, role: string) => {
    await api.patch(`/admin/users/${id}`, { role });
    list.refresh();
  };

  const remove = async (id: number, user: string) => {
    if (!window.confirm(`Delete operator "${user}"? This cannot be undone.`)) return;
    await api.del(`/admin/users/${id}`);
    list.refresh();
  };

  const resetPassword = async () => {
    if (resetId == null || resetPw.length < 8) return;
    await api.post(`/admin/users/${resetId}/password`, { password: resetPw });
    setResetId(null);
    setResetPw("");
    list.refresh();
    setMsg("password reset (sessions invalidated)");
  };

  return (
    <div className="page">
      <PageHeader
        title="Admin Users"
        subtitle="Operator account management — scrypt hashes, role gating, session revocation"
        actions={<Button size="sm" onClick={list.refresh}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={users.length} label="Operators" tone="info" />
        <Stat value={users.filter((u) => u.role === "admin").length} label="Admins" tone="ok" />
        <Stat value={users.filter((u) => u.role === "viewer").length} label="Viewers" tone="info" />
        <Stat value={forbidden ? "restricted" : "ok"} label="Access" tone={forbidden ? "warn" : "ok"} />
      </div>

      {forbidden ? (
        <Panel title="Access denied">
          <Empty icon={<Shield size={16} />} title="Admin privileges required" detail="Sign in as an admin operator to manage accounts." />
        </Panel>
      ) : (
        <>
          <Panel title="Create operator">
            <div className="form-row">
              <Field label="Username">
                <input className="input" value={form.user} onChange={(e) => setForm({ ...form, user: e.target.value })} placeholder="operator-id" autoComplete="off" />
              </Field>
              <Field label="Password (min 8)">
                <input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="••••••••" autoComplete="new-password" />
              </Field>
              <Field label="Role">
                <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="operator">operator</option>
                  <option value="admin">admin</option>
                  <option value="viewer">viewer</option>
                </select>
              </Field>
              <Field label="Create">
                <button className="btn btn-primary" onClick={() => void create()} disabled={busy || !form.user.trim() || form.password.length < 8}>
                  <Plus size={13} /> Create
                </button>
              </Field>
            </div>
            {msg && <p className="tiny" style={{ marginTop: 8 }}>{msg}</p>}
          </Panel>

          <Panel title="Operators" tight>
            {users.length === 0 ? (
              <Empty icon={<Users size={16} />} title="No operators" detail="Create the first admin via Bootstrap, or add one above." />
            ) : (
              <div className="table-wrap">
                <table className="tbl">
                  <thead><tr><th>User</th><th>Role</th><th>Created</th><th /></tr></thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td className="td-strong">{u.user}</td>
                        <td>
                          <select className="input" style={{ width: "auto", padding: "2px 6px" }} value={u.role} onChange={(e) => void changeRole(u.id, e.target.value)}>
                            <option value="admin">admin</option>
                            <option value="operator">operator</option>
                            <option value="viewer">viewer</option>
                          </select>
                        </td>
                        <td className="tiny mute">{new Date(u.created * 1000).toLocaleDateString()}</td>
                        <td>
                          <button className="btn btn-xs" onClick={() => { setResetId(u.id); setResetPw(""); }} title="Reset password"><KeyRound size={11} /></button>{" "}
                          <button className="btn btn-xs" onClick={() => void remove(u.id, u.user)} title="Delete operator"><Trash2 size={11} /></button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {resetId != null && (
            <Panel title="Reset password — session revoked on save">
              <div className="form-row">
                <Field label="New password (min 8)">
                  <input className="input" type="password" value={resetPw} onChange={(e) => setResetPw(e.target.value)} autoComplete="new-password" />
                </Field>
                <Field label="Confirm">
                  <button className="btn btn-primary" disabled={resetPw.length < 8} onClick={() => void resetPassword()}><ShieldCheck size={13} /> Reset</button>{" "}
                  <button className="btn" onClick={() => setResetId(null)}>Cancel</button>
                </Field>
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
