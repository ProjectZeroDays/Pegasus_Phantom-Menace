import { useState } from "react";
import { Bot, MessageSquare, RefreshCw, Send, X } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Select, Textarea } from "@/components/ui";

interface ChatProvider {
  id: string;
  name: string;
  key_present: boolean;
  default_model: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatDock() {
  const [open, setOpen] = useState(false);
  // The provider list sits behind an operator session, so it is only
  // requested once the dock is actually opened.
  const providers = useApi<{ providers: ChatProvider[] }>(open ? "/chat/providers" : null);
  const [provider, setProvider] = useState("venice");
  const [model, setModel] = useState("");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const active = (providers.data?.providers ?? []).find((p) => p.id === provider);

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    const next: Message[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setDraft("");
    setBusy(true);
    setMsg(null);
    try {
      if (provider === "venice") {
        const res = await api.post<{ reply: string }>("/chat/venice", {
          messages: next.map((m) => ({ role: m.role, content: m.content })),
          model: model || undefined,
        });
        setMessages([...next, { role: "assistant", content: res.reply }]);
      } else {
        const res = await api.post<{ reply: string }>("/chat/agent", {
          prompt: text,
          provider: model || undefined,
        });
        setMessages([...next, { role: "assistant", content: res.reply }]);
      }
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "chat request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button className="chat-dock-toggle" onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close chat dock" : "Open chat dock"}>
        {open ? <X size={16} /> : <MessageSquare size={16} />}
      </button>

      {open ? (
        <div className="chat-dock">
          <div className="chat-dock-head">
            <div className="row" style={{ gap: 8 }}>
              <Bot size={14} />
              <span className="mono" style={{ fontSize: 12 }}>CHAT DOCK</span>
            </div>
            <div className="row" style={{ gap: 8 }}>
              <Badge tone={active?.key_present ? "ok" : "dim"}>
                {active?.key_present ? "key set" : "no key"}
              </Badge>
              <Button size="xs" variant="ghost" onClick={() => setMessages([])}>
                <RefreshCw size={11} />
              </Button>
              <Button size="xs" variant="ghost" onClick={() => setOpen(false)}>
                <X size={11} />
              </Button>
            </div>
          </div>

          <div className="row" style={{ gap: 8, padding: "8px 10px" }}>
            <Select value={provider} onChange={setProvider}>
              {(providers.data?.providers ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </Select>
            <input
              className="select mono tiny"
              style={{ flex: 1 }}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={active?.default_model || "model"}
            />
          </div>

          <div className="chat-dock-body">
            {messages.length === 0 ? (
              <div className="tiny mute" style={{ padding: 12 }}>
                Ask the assistant about the current engagement. Venice.ai is proxied
                server side so the key never reaches the browser.
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`chat-msg ${m.role}`}>
                  <span className="mono tiny mute">{m.role}</span>
                  <div>{m.content}</div>
                </div>
              ))
            )}
            {msg ? <div className="mono tiny" style={{ color: "#ff8a5c", padding: "0 10px 8px" }}>{msg}</div> : null}
          </div>

          <div className="chat-dock-foot">
            <Textarea value={draft} onChange={setDraft} rows={2} placeholder="Ask something…" />
            <Button size="sm" variant="primary" onClick={() => void send()} disabled={busy}>
              <Send size={12} /> {busy ? "…" : "Send"}
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
