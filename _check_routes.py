import re
from pathlib import Path

root = Path("pegasus/ui/web/src")
app = (root / "App.tsx").read_text(encoding="utf-8")
nav = (root / "nav.ts").read_text(encoding="utf-8")

routes = sorted(set(re.findall(r'path="([^"]+)"', app)))
navpaths = sorted(set(re.findall(r'path: "([^"]+)"', nav)))

print("routes:", len(routes))
print("nav items:", len(navpaths))
print("nav without route:", [p for p in navpaths if p not in routes])
print("route without nav:", [p for p in routes if p not in navpaths and p != "*"])

# Count page components on disk.
pages = sorted(p.stem for p in (root / "pages").glob("*.tsx"))
print("page files:", len(pages))
print(pages)
