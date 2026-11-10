import { useState } from "react";
import { KeyRound, ShieldCheck, Smartphone, Users } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Field, Input, Panel } from "@/components/ui";
import { PEGASUS_VECTOR } from "@/lib/brand";

export default function AdminLogin() {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const capable = useApi<{ supported: boolean; rp_id: string; origin: string }>(
    "/auth/passkey-capable",
  );

  const submit = async () => {
    if (!user.trim() || !password) {
      setMsg("enter an administrator name and password");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/auth/admin-login", { user: user.trim(), password });
      window.location.href = "/";
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "administrator sign-in failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <img src={PEGASUS_VECTOR} alt="Pegasus" width={40} height={40} />
          <div>
            <div className="mono auth-title">PEGASUS</div>
            <div className="tiny mute">PHANTOM MENACE &middot; administrator</div>
          </div>
          <Badge tone="warn">admin</Badge>
        </div>

        <Panel title="Administrator sign-in"
          actions={<Badge tone={capable.data?.supported ? "ok" : "dim"}>
            {capable.data?.supported ? "passkeys ready" : "passkeys unavailable"}
          </Badge>}>
          <div className="auth-fields">
            <Field label="Administrator">
              <Input value={user} onChange={setUser} placeholder="admin" onEnter={submit} />
            </Field>
            <Field label="Password">
              <Input
                value={password}
                onChange={setPassword}
                type="password"
                placeholder="••••••••"
                onEnter={submit}
              />
            </Field>
            <Button variant="primary" onClick={() => void submit()} disabled={busy}>
              <ShieldCheck size={13} /> {busy ? "verifying…" : "Verify and sign in"}
            </Button>
            {msg ? <div className="mono tiny auth-msg">{msg}</div> : null}
          </div>
        </Panel>

        <div className="auth-links">
          <a href="/login" className="mono tiny"><Users size={11} /> operator sign-in</a>
          <a href="/help" className="mono tiny"><KeyRound size={11} /> password reset</a>
          <a href="/setup" className="mono tiny"><Smartphone size={11} /> first-run setup</a>
        </div>

        <div className="mono tiny mute auth-foot">
          Administrator sessions can manage operators, tunnels and privacy tooling.
        </div>
      </div>
    </div>
  );
}
