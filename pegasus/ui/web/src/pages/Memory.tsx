import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Fact { id: number; key: string; value: string; confidence: number; valid_to: number | null; }

export default function Memory() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [blocks, setBlocks] = useState<Record<string, string>>({});

  const load = () => {
    api.get<{ facts: Fact[] }>("/memory/facts").then((d) => setFacts(d.facts)).catch(() => {});
    api.get<Record<string, string>>("/memory/blocks").then(setBlocks).catch(() => {});
  };

  useEffect(load, []);

  const drop = async (id: number) => { await api.del(`/memory/facts/${id}`); load(); };

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold">Memory</h1>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {Object.entries(blocks).map(([name, body]) => (
          <div key={name} className="rounded border border-white/10 p-2 text-xs">
            <p className="font-mono opacity-60">{name}</p>
            <p className="whitespace-pre-wrap">{body}</p>
          </div>
        ))}
      </div>
      <table className="mt-6 w-full text-xs">
        <thead className="text-left opacity-60">
          <tr><th>Key</th><th>Value</th><th>Conf</th><th>Live</th><th /></tr>
        </thead>
        <tbody>
          {facts.map((f) => (
            <tr key={f.id} className="border-t border-white/5">
              <td className="font-mono">{f.key}</td>
              <td className="truncate">{f.value}</td>
              <td>{f.confidence.toFixed(2)}</td>
              <td>{f.valid_to ? "no" : "yes"}</td>
              <td><button onClick={() => drop(f.id)} className="underline opacity-60">del</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
