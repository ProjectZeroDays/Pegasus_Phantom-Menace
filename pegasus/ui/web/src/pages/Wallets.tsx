import { useState } from "react";
import { Coins, Plus, RefreshCw, Trash2, Wallet } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, Input, PageHeader, Panel, Select, Stat, Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

interface Chain {
  id: string;
  name: string;
  symbol: string;
  decimals: number;
}

interface WalletEntry {
  id: number;
  chain: string;
  address: string;
  label: string;
  notes: string;
  watch_only: boolean;
  created: number;
}

interface Balance {
  chain: string;
  address: string;
  balance: number | null;
  symbol: string | null;
  source: string;
  error?: string;
}

export default function Wallets() {
  const chains = useApi<{ chains: Chain[] }>("/wallets/chains");
  const wallets = useApi<{ wallets: WalletEntry[] }>("/wallets", { interval: 15000 });
  const [chain, setChain] = useState("BTC");
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [balances, setBalances] = useState<Record<number, Balance>>({});

  const items = wallets.data?.wallets ?? [];
  const chainList = chains.data?.chains ?? [];

  const add = async () => {
    if (!address.trim()) {
      setMsg("enter a wallet address");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/wallets", {
        chain,
        address: address.trim(),
        label: label.trim() || undefined,
      });
      setAddress("");
      setLabel("");
      wallets.refresh();
      setMsg("wallet tracked");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "could not track wallet");
    } finally {
      setBusy(false);
    }
  };

  const refreshBalance = async (id: number) => {
    try {
      const res = await api.get<{ balance: Balance }>(`/wallets/${id}/balance`);
      setBalances((prev) => ({ ...prev, [id]: res.balance }));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "balance lookup failed");
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("Stop tracking this wallet?")) return;
    await api.del(`/wallets/${id}`);
    wallets.refresh();
  };

  return (
    <div className="page">
      <PageHeader
        title="Wallet Profiles"
        subtitle="Watch-only addresses per chain. No keys are stored and no transaction is ever signed."
        actions={<Button size="sm" onClick={wallets.refresh}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={items.length} label="Tracked" tone="info" />
        <Stat value={chainList.length} label="Chains" tone="ok" />
        <Stat value={items.every((w) => w.watch_only) ? "watch-only" : "mixed"} label="Mode" tone="warn" />
      </div>

      <Panel title="Track a wallet" actions={<Badge tone="dim">read-only</Badge>}>
        <div className="grid-2" style={{ gap: 10 }}>
          <div className="col">
            <Field label="Chain">
              <Select value={chain} onChange={setChain}>
                {chainList.map((c) => (
                  <option key={c.id} value={c.id}>{c.name} ({c.symbol})</option>
                ))}
              </Select>
            </Field>
          </div>
          <div className="col">
            <Field label="Address">
              <Input value={address} onChange={setAddress} placeholder="address" onEnter={add} />
            </Field>
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <Field label="Label (optional)">
            <Input value={label} onChange={setLabel} placeholder="cold storage" />
          </Field>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 10 }}>
          <Button variant="primary" onClick={() => void add()} disabled={busy}>
            <Plus size={13} /> {busy ? "adding…" : "Track wallet"}
          </Button>
          {msg ? <span className="mono tiny">{msg}</span> : null}
        </div>
      </Panel>

      <Panel title="Tracked wallets">
        {items.length === 0 ? (
          <Empty icon={<Wallet size={22} />} title="No wallets tracked"
            detail="Add an address above to start monitoring public balances." />
        ) : (
          <Table>
            <Thead>
              <Tr>
                <Th>Chain</Th><Th>Label</Th><Th>Address</Th><Th>Balance</Th><Th />
              </Tr>
            </Thead>
            <Tbody>
              {items.map((w) => (
                <Tr key={w.id}>
                  <Td><Badge tone="info">{w.chain}</Badge></Td>
                  <Td>{w.label}</Td>
                  <Td className="mono" style={{ fontSize: 11, wordBreak: "break-all" }}>{w.address}</Td>
                  <Td className="mono">
                    {balances[w.id]
                      ? `${balances[w.id].balance ?? "?"} ${balances[w.id].symbol ?? ""}`
                      : "—"}
                  </Td>
                  <Td>
                    <div className="row" style={{ gap: 6 }}>
                      <Button size="xs" onClick={() => void refreshBalance(w.id)}>
                        <Coins size={11} />
                      </Button>
                      <Button size="xs" variant="danger" onClick={() => void remove(w.id)}>
                        <Trash2 size={11} />
                      </Button>
                    </div>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        )}
      </Panel>
    </div>
  );
}
