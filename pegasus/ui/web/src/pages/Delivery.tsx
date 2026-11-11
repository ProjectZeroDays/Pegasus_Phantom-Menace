import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ChannelHealth, Receipt } from "@/lib/types";

const TONE: Record<string, string> = { sent: "text-info", link: "text-success", error: "text-danger" };

export default function Delivery() {
  const [rows, setRows] = useState<Receipt[]>([]);
  const [health, setHealth] = useState<Record<string, ChannelHealth>>({});

  useEffect(() => {
    api.get<{ receipts: Receipt[] }>("/delivery/receipts").then((d) => setRows(d.receipts));
    api.get<Record<string, ChannelHealth>>("/delivery/health").then(setHealth);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold">Delivery</h1>
      <div className="mt-4 grid grid-cols-2 gap-1 md:grid-cols-4">
        {Object.entries(health).map(([ch, h]) => (
          <div key={ch} className={`rounded border p-2 text-xs ${
            h.state === "ok" ? "border-success" :
            h.state === "link-only" ? "border-warning" : "border-white/10 opacity-50"}`}>
            <p className="font-mono">{ch}</p>
            <p className="opacity-60">{h.reason || h.state}</p>
          </div>
        ))}
      </div>
      <table className="mt-6 w-full text-xs">
        <thead className="text-left opacity-60">
          <tr><th>Time</th><th>Channel</th><th>Target</th><th>Via</th><th>Ref</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-white/5">
              <td>{new Date(r.ts * 1000).toLocaleTimeString()}</td>
              <td className="font-mono">{r.channel}</td>
              <td className="font-mono">{r.target}</td>
              <td className={TONE[r.via]}>{r.via}</td>
              <td className="truncate">{r.ref ?? r.error}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
