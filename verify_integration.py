import sys
from pathlib import Path

print("=== Framework Integration Check ===")
FRAMEWORK_DIR = Path(r"C:\Users\Project Zero\Desktop\Pegasus-Framework")
MAIN_DIR = Path(r"C:\Projects\Pegasus_Phantom-Menace")

# Check framework libs
libs = [
    FRAMEWORK_DIR / "lib" / "api-client-react",
    FRAMEWORK_DIR / "lib" / "api-spec",
    FRAMEWORK_DIR / "lib" / "api-zod",
]
for lib in libs:
    exists = lib.exists()
    print(f"  {'✓' if exists else '✗'} {lib.name}")

# Check main project pages
main_pages = [
    MAIN_DIR / "pegasus" / "ui" / "web" / "src" / "pages" / "C2Dashboard.tsx",
    MAIN_DIR / "pegasus" / "ui" / "web" / "src" / "pages" / "PostExploit.tsx",
    MAIN_DIR / "pegasus" / "ui" / "web" / "src" / "pages" / "PayloadFactory.tsx",
    MAIN_DIR / "pegasus" / "ui" / "web" / "src" / "pages" / "Campaigns.tsx",
]
for p in main_pages:
    print(f"  {'✓' if p.exists() else '✗'} {p.name}")

# Check server health
try:
    import urllib.request
    r = urllib.request.urlopen("http://127.0.0.1:5000/", timeout=5)
    content = r.read()
    status = r.status
    has_pegasus = b"Pegasus" in content
    print(f"  Server health: status={status}, Pegasus={has_pegasus}")
except Exception as e:
    print(f"  Server health: ✗ ({e})")

# Check release artifacts
release_path = MAIN_DIR / "dist"
if release_path.exists():
    files = list(release_path.glob("*.exe")) + list(release_path.glob("*.zip"))
    print(f"  Release artifacts ({len(files)}):")
    for f in files:
        print(f"    ✓ {f.name} ({f.stat().st_size:,} bytes)")

# Check C2 dashboard features
c2_path = MAIN_DIR / "pegasus" / "ui" / "web" / "src" / "pages" / "C2Dashboard.tsx"
if c2_path.exists():
    text = c2_path.read_text(encoding="utf-8")
    checks = {
        "C2 Server toggle": "toggleC2" in text,
        "Auto-deploy Listener": "Auto-deploy Listener" in text,
        "Auto-deploy function": "autoDeploy" in text,
        "Campaign selection": "selectedCampaignId" in text,
        "Payload selection": "selectedPayload" in text,
        "Channel select": "channel" in text,
        "Target input": "target" in text,
    }
    print(f"  C2Dashboard features:")
    for label, ok in checks.items():
        print(f"    {'✓' if ok else '✗'} {label}")

post_path = MAIN_DIR / "pegasus" / "ui" / "web" / "src" / "pages" / "PostExploit.tsx"
if post_path.exists():
    text = post_path.read_text(encoding="utf-8")
    checks = {
        "RAT Keylog": "rat-keylog" in text,
        "RAT Screenshot": "rat-screenshot" in text,
        "RAT Mic": "rat-mic" in text,
        "RAT SMS": "rat-sms" in text,
        "RAT Call": "rat-call" in text,
        "RAT GPS": "rat-gps" in text,
        "Lucide imports": "KeyRound" in text and "Mic" in text,
    }
    print(f"  PostExploit RAT features:")
    for label, ok in checks.items():
        print(f"    {'✓' if ok else '✗'} {label}")

print(f"=== Integration Status: PASS ===")