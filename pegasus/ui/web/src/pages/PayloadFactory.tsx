import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useApi, api } from "@/lib/api";
import { useApp } from "@/state/AppContext";
import {
  Badge,
  Button,
  Card,
  Input,
  Select,
  Table,
  Tbody,
  Th,
  Tr,
  Empty,
  PageHeader,
  Progress,
} from "@/components/ui";

interface Vector {
  key: string;
  cve: string;
  title: string;
  category: string;
  recommended_channels: string[];
}

export default function PayloadFactory() {
  const { activeSerial } = useApp();
  const [categoryFilter, setCategoryFilter] = useState<string>("All");
  const [vectors, setVectors] = useState<Vector[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [output, setOutput] = useState<string>("");

  const categories = ["All", "Polymorphic", "DNA", "Stego", "QR", "SSL Bypass"];
  const filterVectors = (vectors: Vector[]) => {
    if (categoryFilter === "All") return vectors;
    return vectors.filter((v) => v.category.toLowerCase() === categoryFilter.toLowerCase());
  };

  const loadVectors = async () => {
    setLoading(true);
    try {
      const data = await api.get<Vector[]>("/api/catalog");
      setVectors(data);
    } catch (err) {
      setOutput("Error loading vectors: " + (err as any).message);
    } finally {
      setLoading(false);
    }
  };

  const buildAndStage = async (vectorKey: string) => {
    setOutput("building…");
    try {
      const result = await api.post<{ url: string }>("/api/catalog/build", { key: vectorKey, stage: true });
      setOutput(`✅ Staged at ${result.url}`);
    } catch (err) {
      setOutput("❌ Error: " + (err as any).message);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Payload Factory"
        subtitle="Build, stage, and deploy payloads with DNA tagging, stego, QR, and SSL bypass options"
        actions={
          <>
            <Button variant="ghost" onClick={() => void loadVectors()} disabled={loading}>
              <RefreshCw size={13} />
            </Button>
          </>
        }
      />

      <div className="grid" style={{ margin: "12px 0" }}>
        <Card>
          <div className="card-header">Category Filter</div>
          <div className="card-content" style={{ marginTop: "8px" }}>
            <Select
              value={categoryFilter}
              onChange={(v) => setCategoryFilter(v)}
              style={{ width: "100%" }}
            >
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </Select>
          </div>
        </Card>
      </div>

      <div className="grid" style={{ margin: "12px 0" }}>
        {loading ? (
          <div className="card" style={{ textAlign: "center", padding: "20px" }}>
            <Progress value={13} size={13} />
            <div className="muted" style={{ marginTop: "8px" }}>Loading vectors…</div>
          </div>
        ) : (
          <Card>
            <div className="card-header">Available Vectors</div>
            <div className="card-content" style={{ marginTop: "8px" }}>
              {vectors.length === 0 ? (
                <Empty title="No vectors match filter" />
              ) : (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>CVE</th>
                      <th>Title</th>
                      <th>Category</th>
                      <th>Channels</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vectors.map((v) => (
                      <tr key={v.key}>
                        <td className="mono">{v.cve}</td>
                        <td>{v.title}</td>
                        <td className="muted">{v.category}</td>
                        <td className="muted small">{v.recommended_channels.join(", ")}</td>
                        <td className="mono">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => void buildAndStage(v.key)}
                          >
                            Build & Stage
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Card>
        )}
      </div>

      {output && <div className="card" style={{ marginTop: "16px" }}>{output}</div>}
    </div>
  );
}