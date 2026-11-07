"""fix_sweep.py - 11.1 filterVectors, 12.5 env docs, pytest collection."""
import re
import sys
import pathlib

# ---------- 11.1 ----------
pf = pathlib.Path("pegasus/ui/web/src/pages/PayloadFactory.tsx")
src = pf.read_text(encoding="utf-8")
lines = src.splitlines()

print("=== filterVectors definition + vector usages ===")
for i, ln in enumerate(lines, 1):
    if "filterVectors" in ln or re.search(r"\bvectors\b", ln):
        print("%4d|%s" % (i, ln.rstrip()))

if len(re.findall(r"\bfilterVectors\b", src)) > 1:
    print("\nskip  filterVectors already called")
else:
    cands = [m.start() for m in re.finditer(r"\bvectors\.map\(", src)]
    if cands:
        src = re.sub(r"(?<![\w.])vectors\.map\(", "filterVectors(vectors).map(", src, count=1)
        pf.write_text(src, encoding="utf-8")
        print("\nok    wired: filterVectors(vectors).map(")
    else:
        print("\nMISS  no vectors.map( call site")
        for i, ln in enumerate(lines, 1):
            if ".map(" in ln:
                print("      %4d|%s" % (i, ln.strip()[:100]))

# ---------- 12.5 ----------
doc_targets = [pathlib.Path("pegasus/ui/web/README.md"), pathlib.Path("README.md")]
doc = next((p for p in doc_targets if p.exists()), None)

SECTION = """
## Frontend environment

The web client reads two build-time variables. Both are optional.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE` | `/api` | Base path or absolute origin for every API call. Set it when the UI is served from a different host than the backend, e.g. `VITE_API_BASE=https://10.1.10.27:5001/api`. |
| `VITE_PEGASUS_API_TOKEN` | unset | Baked-in bearer token. Sent as `X-Pegasus-Token` on every request. Only useful when `PEGASUS_REQUIRE_AUTH=1`; otherwise leave it out so the token can be set at runtime with `setApiToken()` from the console. |

`VITE_API_BASE` is read once at module load in `src/lib/api.ts` and again in `src/pages/Media.tsx`; changing it requires a rebuild.

### Auth

The backend gate is opt-in. With `PEGASUS_REQUIRE_AUTH` unset every route is public, which is the default for local use. To lock it down:

```bash
set PEGASUS_REQUIRE_AUTH=1
set PEGASUS_API_TOKEN=<long random string>