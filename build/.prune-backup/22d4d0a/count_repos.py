import re
with open("scripts/bundle.txt") as f:
    content = f.read()
repos = set()
for line in content.splitlines():
    if "Q4_K_M" in line or "mlx" in line:
        for match in re.findall(r'"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)"', line):
            repos.add(match)
print("Unique repos in bundle:", len(repos))
for r in sorted(repos):
    print(" ", r)
