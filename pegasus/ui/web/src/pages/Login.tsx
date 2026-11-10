import { useState } from "react";
import { useLocation } from "wouter";
import { KeyRound, LogIn, ShieldCheck, Smartphone } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Badge, Button, Field, Input, Panel } from "@/components/ui";
import { PEGASUS_VECTOR } from "@/lib/brand";

export default function Login() {
  const [, navigate] = useLocation();
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const submit = async () => {
    if (!user.trim() || !password) {
      setMsg("enter an operator name and password");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/auth/login", { user: user.trim(), password });
      window.location.href = "/";
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "sign-in failed");
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
            <div className="tiny mute">PHANTOM MENACE &middot; operator sign-in</div>
          </div>
        </div>

        <Panel title="Sign in">
          <div className="auth-fields">
            <Field label="Operator">
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
              <LogIn size={13} /> {busy ? "signing in…" : "Sign in"}
            </Button>
            {msg ? <div className="mono tiny auth-msg">{msg}</div> : null}
          </div>
        </Panel>

        <div className="auth-links">
          <a href="/admin-login" className="mono tiny">
            <ShieldCheck size={11} /> administrator sign-in
          </a>
          <a href="/help" className="mono tiny">
            <KeyRound size={11} /> password reset &amp; help
          </a>
          <a href="/setup" className="mono tiny">
            <Smartphone size={11} /> first-run setup
          </a>
        </div>

        <div className="mono tiny mute auth-foot">
          Authorized security testing only. Sessions expire after 24 hours.
          <Badge tone="dim">v2.2</Badge>
        </div>
      </div>
    </div>
  );
}
