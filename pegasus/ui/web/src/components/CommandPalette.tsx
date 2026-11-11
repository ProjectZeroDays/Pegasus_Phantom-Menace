import { useState } from "react";
import { api } from "@/lib/api";

interface Guess { command: string | null; confidence: number; why: string; }

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [guess, setGuess] = useState<Guess | null>(null);

  const send = async (execute: boolean) => {
    if (!text.trim()) return;
    const g = await api.post<Guess>("/nl/command", { text, execute });
    setGuess(g);
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} aria-label="Ask in plain English"
        className="fixed bottom-5 right-5 z-40 grid h-12 w-12 place-items-center rounded-full bg-primary text-accent-contrast shadow-lg">
        N
      </button>
    );
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 w-80 rounded-lg border border-line bg-surface p-3 shadow-2xl">
      <div className="flex justify-between text-xs opacity-60">
        <span>Ask in plain English</span>
        <button onClick={() => setOpen(false)}>x</button>
      </div>
      <input autoFocus value={text} onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") void send(true); }}
        placeholder="dump sms from the connected phone"
        className="mt-2 w-full rounded border bg-transparent px-2 py-1 text-sm" />
      {guess && (
        <div className="mt-2 rounded bg-white/5 p-2 text-xs">
          {guess.command ? (
            <>
              <p className="font-mono">{guess.command}</p>
              <p className="opacity-60">{Math.round(guess.confidence * 100)}% Â· {guess.why}</p>
            </>
          ) : <p className="opacity-60">No match â€” {guess.why}</p>}
        </div>
      )}
    </div>
  );
}
