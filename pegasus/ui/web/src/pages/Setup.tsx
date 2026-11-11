import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ModelPicker } from "@/components/ModelPicker";

export default function Setup() {
  const [picked, setPicked] = useState<Record<string, string | null>>({ planner: null, coder: null });
  const [error, setError] = useState<string | null>(null);
  const ready = Boolean(picked.planner);

  useEffect(() => { api.get("/setup/state").catch((e) => setError(e.message)); }, []);

  const save = async () => {
    try {
      await api.post("/setup/skip");
      location.assign("/");
    } catch (e) { setError((e as Error).message); }
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-semibold">First run</h1>
      <p className="mt-1 text-sm opacity-60">
        Pick a provider key or a local model. One of the two is required.
      </p>
      <div className="mt-8 grid gap-8 md:grid-cols-2">
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase opacity-70">Planner</h2>
          <p className="mb-2 text-xs opacity-50">Smallest model that holds a schema.</p>
          <ModelPicker role="planner" onPick={(id) => setPicked({ ...picked, planner: id })} />
        </section>
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase opacity-70">Coder</h2>
          <p className="mb-2 text-xs opacity-50">Larger is better here. Falls back to the planner.</p>
          <ModelPicker role="coder" onPick={(id) => setPicked({ ...picked, coder: id })} />
        </section>
      </div>
      {error && <p className="mt-3 text-xs text-danger">{error}</p>}
      <button disabled={!ready} onClick={save}
        className="mt-6 rounded bg-primary px-4 py-2 text-sm text-accent-contrast disabled:opacity-40">
        {picked.coder ? "Continue" : "Continue with one model"}
      </button>
    </div>
  );
}
