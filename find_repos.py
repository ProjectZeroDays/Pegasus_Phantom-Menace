import re
with open("pegasus/modules/ai/catalog.py") as f:
    content = f.read()
repos = set(re.findall(r'"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)"', content))
print("Repos:", len(repos))
for r in sorted(repos):
    print(" ", r)
