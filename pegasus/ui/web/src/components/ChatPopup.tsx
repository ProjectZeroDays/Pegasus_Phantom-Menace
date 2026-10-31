import { useState, useRef, useEffect } from "react";
import { Sparkles, Send, X, ChevronUp, ChevronDown, Settings2 } from "lucide-react";
import { Link } from "wouter";
import { api } from "@/lib/api";

interface NlGuess {
  command: string | null;
  confidence: number;
  why: string;
  executed?: boolean;
  job?: { id: string; status: string };
}

export function ChatPopup() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ text: string; from: "user" | "bot" }[]>([
    { text: "Ask me anything — I'll translate it into a command and run it.", from: "bot" },
  ]);
  const [guess, setGuess] = useState<NlGuess | null>(null);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, guess]);

  const send = async (execute: boolean) => {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setMessages((prev) => [...prev, { text, from: "user" }]);
    setInput("");
    setGuess(null);
    try {
      const r = await api.post<NlGuess>("/nl/command", { text, execute });
      if (r.command && execute && r.executed && r.job) {
        setMessages((prev) => [...prev, { text: `Queued ${r.command} — job ${r.job!.id}`, from: "bot" }]);
      } else if (r.command && !execute) {
        setGuess(r);
        setMessages((prev) => [...prev, { text: `Guess: ${r.command} (${(r.confidence * 100).toFixed(0)}%) — ${r.why}`, from: "bot" }]);
      } else if (r.command && execute && !r.executed) {
        setGuess(r);
        setMessages((prev) => [...prev, { text: `Low confidence (${(r.confidence * 100).toFixed(0)}%) — confirm below.`, from: "bot" }]);
      } else {
        setMessages((prev) => [...prev, { text: r.why || "No matching command — try rephrasing.", from: "bot" }]);
      }
    } catch (e: any) {
      setMessages((prev) => [...prev, { text: `error: ${e?.message ?? "failed"}`, from: "bot" }]);
    } finally {
      setBusy(false);
    }
  };

  const confirmRun = async () => {
    if (!guess?.command) return;
    const cmd = guess.command;
    setGuess(null);
    try {
      const r = await api.post<NlGuess>("/nl/command", { text: cmd, execute: true });
      setMessages((prev) => [...prev, { text: r.executed && r.job ? `Queued ${cmd} — job ${r.job.id}` : `couldn't execute ${cmd}`, from: "bot" }]);
    } catch (e: any) {
      setMessages((prev) => [...prev, { text: `error: ${e?.message ?? "failed"}`, from: "bot" }]);
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50" style={{ width: open ? 340 : 56 }}>
      <div className="bg-[#12131a]/95 border border-white/5 rounded-xl shadow-2xl backdrop-blur-md overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2.5 text-sm text-slate-200">
          <button
            onClick={() => setOpen(!open)}
            className="flex items-center gap-2 flex-1 text-left hover:text-white transition"
            aria-label="Toggle assistant"
          >
            {open ? <ChevronDown size={15} className="text-[#ff9e00]" /> : <ChevronUp size={15} className="text-[#ff9e00]" />}
            <Sparkles size={15} className="text-[#ff9e00]" />
            <span className="flex-1 truncate">Pegasus Assistant</span>
          </button>
          {open && (
            <Link href="/settings#agents" aria-label="Agent settings" title="Agent settings">
              <Settings2 size={13} className="text-slate-500 hover:text-slate-200" />
            </Link>
          )}
          <span className="text-[10px] text-slate-500">v2.1</span>
        </div>
        {open && (
          <div className="flex flex-col h-72">
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-2 text-xs leading-relaxed">
              {messages.map((m, i) => (
                <div key={i} className={`${m.from === "bot" ? "text-slate-300" : "text-white font-medium text-right"}`}>
                  {m.from === "bot" ? <Sparkles size={10} className="inline-block text-[#ff9e00] mr-1 mb-0.5" /> : null}
                  <span>{m.text}</span>
                </div>
              ))}
              {guess?.command && !guess.executed && (
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => void confirmRun()}
                    className="text-[10px] px-2 py-1 rounded bg-[#ff9e00]/20 text-[#ff9e00] hover:bg-[#ff9e00]/30"
                  >
                    Run {guess.command}
                  </button>
                  <button
                    onClick={() => setGuess(null)}
                    className="text-[10px] px-2 py-1 rounded bg-white/5 text-slate-400 hover:bg-white/10"
                  >
                    Rephrase
                  </button>
                </div>
              )}
              {busy && <div className="text-slate-500 text-[10px]">thinking…</div>}
            </div>
            <div className="border-t border-white/5 px-2 py-2 flex items-center gap-1.5">
              <input
                className="flex-1 bg-[#1a1b26] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-[#ff9e00]/40"
                placeholder="Type a request..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void send(guess?.command ? false : true);
                }}
              />
              <button
                onClick={() => void send(true)}
                disabled={busy}
                className="text-[#ff9e00] hover:text-[#ffb84d] disabled:opacity-40"
                aria-label="Send"
              >
                <Send size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
