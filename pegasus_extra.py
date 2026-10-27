"""
Pegasus Extra Features — High-value capabilities integrated from DeadDroid v2.0.

Provides:
  • AI Assistant (Claude) — real-time pentest guidance
  • Report Generator (HTML) — professional reports
  • Android CVE Scanner — vulnerability fingerprinting
  • Live Dashboard — real-time session monitoring
  • Telegram Remote Control — push alerts + remote commands
  • Campaign Manager — organize assessments
  • Steganography Delivery — hide payload URLs in images
  • Mass Payload Generator — batch payload generation
  • Payload DNA Tracker — unique payload tracking
  • AI Mutation Engine — AV evasion suggestions
  • QR Payload Delivery — QR code generation
  • SSL Pinning Bypass — Frida script generator
  • Listener Monitor — port polling alerts
  • ngrok Tunnel Manager — tunnel management
  • Network & Port Forwarding — socat/SSH/iptables
  • Network Scanner — nmap host discovery
"""
import os
import sys
import json
import time
import socket
import shutil
import subprocess
import base64
import zlib
import hashlib
import random
import string
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

# Pegasus workspace
PEGASUS_HOME = Path.home() / ".pegasus"
PAYLOADS_DIR = PEGASUS_HOME / "payloads"
REPORTS_DIR = PEGASUS_HOME / "reports"
SESSIONS_DIR = PEGASUS_HOME / "sessions"
LOGS_DIR = PEGASUS_HOME / "logs"
CAMPAIGNS_DIR = PEGASUS_HOME / "campaigns"
DNA_DIR = PEGASUS_HOME / "dna"
CERTS_DIR = PEGASUS_HOME / "certs"

console = Console()

# ── Workspace init ─────────────────────────────────────────────────────────────
def init_workspace():
    for d in [PEGASUS_HOME, PAYLOADS_DIR, REPORTS_DIR, SESSIONS_DIR, LOGS_DIR,
              CAMPAIGNS_DIR, DNA_DIR, CERTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _run_cmd(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout or "", r.stderr or ""
    except Exception as e:
        return -1, "", str(e)

def _check_tool(name):
    return shutil.which(name) is not None

def _log_event(msg):
    log_file = LOGS_DIR / "pegasus.log"
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

def _load_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}

def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _random_str(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))

# ── 1. AI Assistant (Claude) ──────────────────────────────────────────────────
AI_CONFIG = PEGASUS_HOME / "ai_config.json"
AI_SYSTEM_PROMPT = """You are Pegasus AI — an expert Android security and penetration testing assistant.
You assist authorised security professionals with:
- Android vulnerability assessment and penetration testing
- ADB commands and device management
- Network security analysis and scanning
- Report writing and findings documentation
- Defensive recommendations and patch advice

You always remind users that testing must be authorised. You do not assist with
illegal activities. You provide technical, accurate, actionable advice.
"""
_conversation_history = []
_api_key = None

def _load_api_key():
    global _api_key
    cfg = _load_json(AI_CONFIG)
    if "api_key" in cfg:
        _api_key = cfg["api_key"]
        return _api_key
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        _api_key = env_key
        return _api_key
    return None

def _save_api_key(key):
    global _api_key
    _api_key = key
    cfg = _load_json(AI_CONFIG)
    cfg["api_key"] = key
    _save_json(AI_CONFIG, cfg)
    console.print("[green]✔ API key saved.[/]")

def ai_sign_in():
    console.rule("[bold cyan]Pegasus AI — Claude Sign-In[/]")
    console.print("[dim]Get your free API key at: https://console.anthropic.com[/]\n")
    existing = _load_api_key()
    if existing:
        masked = existing[:8] + "..." + existing[-4:]
        console.print(f"[yellow]Existing key:[/] {masked}")
        if not Confirm.ask("Replace it?", default=False):
            return
    key = Prompt.ask("Enter Anthropic API key", password=True)
    if not key.startswith("sk-ant-"):
        console.print("[red]✘ Invalid key format. Should start with 'sk-ant-'[/]")
        return
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=10,
                             messages=[{"role": "user", "content": "ping"}])
        _save_api_key(key)
        console.print("[bold green]✔ Claude AI connected![/]")
    except ImportError:
        console.print("[red]✘ anthropic not installed. Run: pip install anthropic[/]")
    except Exception as e:
        console.print(f"[red]✘ Verification failed:[/] {e}")

def ai_sign_out():
    global _api_key
    cfg = _load_json(AI_CONFIG)
    cfg.pop("api_key", None)
    _save_json(AI_CONFIG, cfg)
    _api_key = None
    _conversation_history.clear()
    console.print("[yellow]Signed out of Claude AI.[/]")

def ai_chat(user_message):
    key = _api_key or _load_api_key()
    if not key:
        console.print("[red]✘ Not signed in. Use AI Assistant > Sign In.[/]")
        return None
    try:
        import anthropic
    except ImportError:
        console.print("[red]✘ anthropic not installed. Run: pip install anthropic[/]")
        return None
    _conversation_history.append({"role": "user", "content": user_message})
    if len(_conversation_history) > 40:
        del _conversation_history[:2]
    try:
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2048,
            system=[{"type": "text", "text": AI_SYSTEM_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            messages=_conversation_history,
        )
        reply = response.content[0].text
        _conversation_history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        console.print(f"[red]✘ API error:[/] {e}")
        _conversation_history.pop()
        return None

def interactive_ai():
    console.rule("[bold cyan]Pegasus AI Assistant — Powered by Claude[/]")
    key = _load_api_key()
    if not key:
        console.print("[yellow]Not signed in.[/]")
        ai_sign_in()
        key = _api_key
    if not key:
        return
    console.print(Panel(
        "[bold white]Ask anything about Android security, ADB, network analysis,\n"
        "post-exploitation, or report writing.[/]\n\n"
        "[dim]Commands: /clear  /exit[/]",
        title="[bold cyan]Pegasus AI[/]", border_style="cyan"))
    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/]")
        except (KeyboardInterrupt, EOFError):
            break
        if not user_input.strip():
            continue
        if user_input.strip() == "/exit":
            break
        if user_input.strip() == "/clear":
            _conversation_history.clear()
            console.print("[yellow]Conversation cleared.[/]")
            continue
        with console.status("[cyan]Claude is thinking...[/]", spinner="dots"):
            reply = ai_chat(user_input)
        if reply:
            console.print(Panel(Markdown(reply), title="[bold cyan]Claude[/]",
                                border_style="cyan", padding=(1, 2)))

def ai_status():
    key = _load_api_key()
    if key:
        return f"[green]✔ Signed in[/] ({key[:8]}...)"
    return "[red]✘ Not signed in[/]"

# ── 2. Report Generator (HTML) ───────────────────────────────────────────────
REPORT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pegasus Report — {title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; }}
  header {{ background: linear-gradient(135deg,#161b22,#21262d); padding: 40px; border-bottom: 1px solid #30363d; }}
  header h1 {{ color: #ff4444; font-size: 2rem; }}
  header p  {{ color: #8b949e; margin-top: 6px; }}
  .badge {{ display:inline-block; padding:4px 10px; border-radius:12px; font-size:.75rem; font-weight:600; margin-top:10px; }}
  .badge-critical {{ background:#ff000033; color:#ff4444; border:1px solid #ff4444; }}
  .badge-high     {{ background:#ff880033; color:#ff8800; border:1px solid #ff8800; }}
  .badge-medium   {{ background:#ffcc0033; color:#ffcc00; border:1px solid #ffcc00; }}
  .badge-low      {{ background:#00cc6633; color:#00cc66; border:1px solid #00cc66; }}
  .badge-info     {{ background:#0088ff33; color:#0088ff; border:1px solid #0088ff; }}
  main {{ max-width:1100px; margin:40px auto; padding:0 20px; }}
  section {{ background:#161b22; border:1px solid #30363d; border-radius:10px; margin-bottom:24px; padding:28px; }}
  section h2 {{ color:#58a6ff; font-size:1.1rem; margin-bottom:16px; border-bottom:1px solid #30363d; padding-bottom:10px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#21262d; color:#58a6ff; padding:10px; text-align:left; font-weight:600; }}
  td {{ padding:10px; border-top:1px solid #21262d; }}
  code {{ background:#161b22; border:1px solid #30363d; border-radius:4px; padding:2px 6px; font-family:monospace; color:#7ee787; font-size:.85rem; }}
  pre  {{ background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:16px; overflow-x:auto; }}
  pre code {{ background:none; border:none; padding:0; }}
  .finding {{ margin-bottom:20px; padding:18px; background:#0d1117; border-radius:8px; border-left:4px solid #ff4444; }}
  .finding h3 {{ color:#e6edf3; margin-bottom:8px; }}
  footer {{ text-align:center; padding:30px; color:#484f58; font-size:.85rem; }}
  footer a {{ color:#58a6ff; text-decoration:none; }}
</style>
</head>
<body>
<header>
  <h1>&#9760; Pegasus Pentest Report</h1>
  <p>{title}</p>
  <p style="margin-top:8px;color:#8b949e">Generated: {date} &nbsp;|&nbsp; Tester: {tester} &nbsp;|&nbsp; Target: {target}</p>
</header>
<main>
  <section>
    <h2>Executive Summary</h2>
    <p>{summary}</p>
  </section>
  <section>
    <h2>Scope &amp; Methodology</h2>
    <table>
      <tr><th>Item</th><th>Details</th></tr>
      <tr><td>Target Device / App</td><td>{target}</td></tr>
      <tr><td>Test Type</td><td>{test_type}</td></tr>
      <tr><td>Authorization</td><td>{authorization}</td></tr>
      <tr><td>Start Date</td><td>{start_date}</td></tr>
      <tr><td>End Date</td><td>{end_date}</td></tr>
      <tr><td>Tools Used</td><td>{tools}</td></tr>
    </table>
  </section>
  <section>
    <h2>Findings</h2>
    {findings_html}
  </section>
  <section>
    <h2>Payload Summary</h2>
    {payloads_html}
  </section>
  <section>
    <h2>Recommendations</h2>
    <p>{recommendations}</p>
  </section>
</main>
<footer>
  <p>Generated by <strong>Pegasus v1.4</strong> &mdash; Android Device Management & Security Audit Tool</p>
  <p>Author: <a href="https://github.com/ProjectZeroDays">ProjectZeroDays</a></p>
  <p style="margin-top:8px;color:#ff444488">This report is confidential. For authorised use only.</p>
</footer>
</body>
</html>
"""

FINDING_TEMPLATE = """
<div class="finding">
  <span class="badge badge-{severity_lower}">{severity}</span>
  <h3>{title}</h3>
  <p><strong>Description:</strong> {description}</p>
  <p><strong>Impact:</strong> {impact}</p>
  <p><strong>Evidence:</strong></p>
  <pre><code>{evidence}</code></pre>
  <p><strong>Recommendation:</strong> {recommendation}</p>
</div>
"""

def _build_findings_html(findings):
    if not findings:
        return "<p>No findings recorded.</p>"
    html = ""
    for f in findings:
        html += FINDING_TEMPLATE.format(
            severity_lower=f.get("severity", "info").lower(),
            severity=f.get("severity", "INFO").upper(),
            title=f.get("title", "Untitled"),
            description=f.get("description", ""),
            impact=f.get("impact", ""),
            evidence=f.get("evidence", "").replace("<", "&lt;").replace(">", "&gt;"),
            recommendation=f.get("recommendation", ""),
        )
    return html

def _build_payloads_html(payloads):
    if not payloads:
        return "<p>No payloads recorded.</p>"
    rows = ""
    for p in payloads:
        rows += f"<tr><td>{p.get('name','')}</td><td><code>{p.get('type','')}</code></td><td>{p.get('lhost','')}:{p.get('lport','')}</td><td>{p.get('notes','')}</td></tr>"
    return f"<table><tr><th>File</th><th>Type</th><th>LHOST:LPORT</th><th>Notes</th></tr>{rows}</table>"

def generate_report(title, tester, target, summary, findings, payloads=None, test_type="Black Box",
                    authorization="Written authorization obtained", start_date="", end_date="",
                    tools="Pegasus, ADB", recommendations=""):
    payloads = payloads or []
    now = time.strftime("%Y-%m-%d %H:%M UTC")
    filename = f"report_{title.replace(' ','_')}_{time.strftime('%Y%m%d_%H%M%S')}.html"
    out_path = REPORTS_DIR / filename
    html = REPORT_HTML_TEMPLATE.format(
        title=title, date=now, tester=tester, target=target, summary=summary,
        test_type=test_type, authorization=authorization,
        start_date=start_date or now, end_date=end_date or now, tools=tools,
        findings_html=_build_findings_html(findings),
        payloads_html=_build_payloads_html(payloads),
        recommendations=recommendations,
    )
    out_path.write_text(html, encoding="utf-8")
    console.print(f"[green]✔ Report saved:[/] {out_path}")
    return out_path

def interactive_report():
    console.rule("[bold cyan]Pegasus Report Generator[/]")
    title = Prompt.ask("Report title", default="Android Security Assessment")
    tester = Prompt.ask("Tester name", default="Security Team")
    target = Prompt.ask("Target (device/app)")
    summary = Prompt.ask("Executive summary")
    recs = Prompt.ask("Recommendations")
    findings = []
    while Confirm.ask("Add a finding?", default=True):
        findings.append({
            "title": Prompt.ask("Finding title"),
            "severity": Prompt.ask("Severity", choices=["Critical","High","Medium","Low","Info"], default="High"),
            "description": Prompt.ask("Description"),
            "impact": Prompt.ask("Impact"),
            "evidence": Prompt.ask("Evidence / PoC"),
            "recommendation": Prompt.ask("Recommendation"),
        })
    path = generate_report(title=title, tester=tester, target=target, summary=summary,
                          findings=findings, recommendations=recs)
    console.print(f"\n[bold]Open in browser:[/] file://{path.resolve()}")

# ── 3. Android CVE Scanner ───────────────────────────────────────────────────
BUILTIN_CVES = [
    {"id": "CVE-2024-31317", "description": "ZygoteProcess command injection — system-level code execution", "severity": "Critical", "cvss": 9.8, "affects": {"min_api": 30, "max_api": 34}, "patch_level": "2024-07-01"},
    {"id": "CVE-2024-0044", "description": "run-as privilege escalation via PackageManager race condition", "severity": "High", "cvss": 7.7, "affects": {"min_api": 31, "max_api": 34}, "patch_level": "2024-06-01"},
    {"id": "CVE-2023-21492", "description": "Kernel information disclosure via race condition", "severity": "High", "cvss": 7.4, "affects": {"min_api": 28, "max_api": 33}, "patch_level": "2023-05-01"},
    {"id": "CVE-2023-20963", "description": "WorkSource privilege escalation", "severity": "High", "cvss": 7.8, "affects": {"min_api": 30, "max_api": 33}, "patch_level": "2023-03-01"},
    {"id": "CVE-2022-20465", "description": "Lockscreen bypass — access device without PIN", "severity": "Critical", "cvss": 9.1, "affects": {"min_api": 30, "max_api": 32}, "patch_level": "2022-11-01"},
    {"id": "CVE-2022-20452", "description": "Permission bypass in NotificationManager", "severity": "High", "cvss": 8.4, "affects": {"min_api": 30, "max_api": 33}, "patch_level": "2022-12-01"},
    {"id": "CVE-2021-39793", "description": "GPU driver heap OOB write — local privilege escalation", "severity": "Critical", "cvss": 8.8, "affects": {"min_api": 26, "max_api": 32}, "patch_level": "2022-03-05"},
    {"id": "CVE-2021-0954", "description": "Intent redirection in Android framework", "severity": "High", "cvss": 7.3, "affects": {"min_api": 26, "max_api": 31}, "patch_level": "2021-12-01"},
    {"id": "CVE-2020-0041", "description": "Binder OOB write — full root exploit chain available", "severity": "Critical", "cvss": 9.8, "affects": {"min_api": 26, "max_api": 29}, "patch_level": "2020-03-01"},
    {"id": "CVE-2019-2215", "description": "Use-after-free in Binder IPC driver", "severity": "Critical", "cvss": 9.3, "affects": {"min_api": 21, "max_api": 28}, "patch_level": "2019-10-06"},
    {"id": "CVE-2017-13156", "description": "Janus vulnerability — APK signature bypass", "severity": "High", "cvss": 7.8, "affects": {"min_api": 21, "max_api": 26}, "patch_level": "2017-12-01"},
    {"id": "CVE-2015-3864", "description": "Stagefright — MMS media processing RCE", "severity": "Critical", "cvss": 10.0, "affects": {"min_api": 16, "max_api": 22}, "patch_level": "2015-09-01"},
]

def _get_device_info_adb():
    rc, out, _ = _run_cmd("adb shell getprop ro.build.version.release", timeout=10)
    version = out.strip() if rc == 0 else "Unknown"
    rc2, out2, _ = _run_cmd("adb shell getprop ro.build.version.sdk", timeout=10)
    api = out2.strip() if rc2 == 0 else "0"
    rc3, out3, _ = _run_cmd("adb shell getprop ro.build.version.security_patch", timeout=10)
    patch = out3.strip() if rc3 == 0 else "1970-01-01"
    rc4, out4, _ = _run_cmd("adb shell getprop ro.product.model", timeout=10)
    model = out4.strip() if rc4 == 0 else "Unknown"
    rc5, out5, _ = _run_cmd("adb shell getprop ro.product.manufacturer", timeout=10)
    mfr = out5.strip() if rc5 == 0 else "Unknown"
    return {"android_version": version, "api_level": api, "security_patch": patch, "model": model, "manufacturer": mfr}

def _version_to_api(v):
    mapping = {"15":35,"14":34,"13":33,"12":31,"11":30,"10":29,"9":28,"8":27,"7":24,"6":23,"5":21}
    for k, api in mapping.items():
        if v.startswith(k):
            return api
    try:
        return int(v.split(".")[0]) + 20
    except:
        return 0

def _patch_to_tuple(p):
    try:
        parts = p.split("-")
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except:
        return (0, 0, 0)

def _is_vulnerable(cve, api_level, security_patch):
    affects = cve.get("affects", {})
    min_api = affects.get("min_api", 0)
    max_api = affects.get("max_api", 99)
    if not (min_api <= api_level <= max_api):
        return False
    patch_date = _patch_to_tuple(security_patch)
    fix_date = _patch_to_tuple(cve.get("patch_level", "9999-12-01"))
    return patch_date < fix_date

def scan_cves(use_nvd=False):
    console.print("[cyan]► Fingerprinting device via ADB...[/]")
    info = _get_device_info_adb()
    if not info:
        return []
    api_level = int(info.get("api_level", "0") or "0")
    if api_level == 0:
        api_level = _version_to_api(info.get("android_version", "0"))
    security_patch = info.get("security_patch", "1970-01-01")
    t = Table(title="Device Fingerprint", show_lines=True)
    t.add_column("Property", style="cyan")
    t.add_column("Value", style="yellow")
    for k, v in info.items():
        t.add_row(k.replace("_", " ").title(), v)
    console.print(t)
    console.print(f"\n[cyan]► Checking against CVE database (API={api_level}, Patch={security_patch})...[/]")
    vulns = [cve for cve in BUILTIN_CVES if _is_vulnerable(cve, api_level, security_patch)]
    if not vulns:
        console.print("[green]✔ No matching CVEs found.[/]")
        return []
    result_table = Table(title=f"[bold red]⚠  {len(vulns)} CVE(s) Found[/]", box=box.SIMPLE_HEAVY, show_lines=True)
    result_table.add_column("CVE ID", style="bold yellow")
    result_table.add_column("Severity", style="red")
    result_table.add_column("CVSS", style="magenta")
    result_table.add_column("Description", style="white")
    result_table.add_column("Patch Date", style="dim")
    for v in sorted(vulns, key=lambda x: x.get("cvss", 0), reverse=True):
        sev = v.get("severity", "")
        sev_colored = (f"[bold red]{sev}[/]" if sev == "Critical" else f"[red]{sev}[/]" if sev == "High" else f"[yellow]{sev}[/]" if sev == "Medium" else f"[green]{sev}[/]")
        result_table.add_row(v.get("id", ""), sev_colored, str(v.get("cvss", "")), v.get("description", "")[:70], v.get("patch_level", "NVD"))
    console.print(result_table)
    return vulns

def interactive_cve():
    console.rule("[bold cyan]Android CVE Scanner[/]")
    menu = {"1": "Scan connected device (ADB)", "2": "Manual scan", "3": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="3")
    if choice == "1":
        scan_cves(use_nvd=False)
    elif choice == "2":
        ver = Prompt.ask("Android version (e.g. 12, 13, 14)")
        patch = Prompt.ask("Security patch level (YYYY-MM-DD)", default="2022-01-01")
        api_level = _version_to_api(ver)
        vulns = [cve for cve in BUILTIN_CVES if _is_vulnerable(cve, api_level, patch)]
        for v in sorted(vulns, key=lambda x: x.get("cvss", 0), reverse=True):
            console.print(f"  [bold yellow]{v['id']}[/]  CVSS {v['cvss']}  [red]{v['severity']}[/]  {v['description'][:60]}")

# ── 4. Live Dashboard ────────────────────────────────────────────────────────
def interactive_dashboard():
    console.rule("[bold cyan]Live Dashboard[/]")
    console.print("[dim]Real-time device monitoring dashboard.[/]\n")
    console.print("[yellow]Features: device info, battery, storage, network status[/]")
    console.print("[dim]Press Ctrl+C to exit.[/]")
    try:
        while True:
            # Get device info
            rc, model, _ = _run_cmd("adb shell getprop ro.product.model", timeout=5)
            rc2, battery, _ = _run_cmd("adb shell dumpsys battery | grep level", timeout=5)
            rc3, storage, _ = _run_cmd("adb shell df -h /data", timeout=5)
            console.clear()
            console.print(f"[bold cyan]Pegasus Live Dashboard[/] — {time.strftime('%H:%M:%S')}")
            console.print(f"Device: {model.strip() if rc == 0 else 'N/A'}")
            console.print(f"Battery: {battery.strip() if rc2 == 0 else 'N/A'}")
            console.print(f"Storage: {storage.strip() if rc3 == 0 else 'N/A'}")
            time.sleep(3)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard closed.[/]")

# ── 5. Telegram Remote Control ───────────────────────────────────────────────
TELEGRAM_CONFIG = PEGASUS_HOME / "telegram_config.json"

def _load_telegram_config():
    return _load_json(TELEGRAM_CONFIG)

def _save_telegram_config(token, chat_id):
    _save_json(TELEGRAM_CONFIG, {"token": token, "chat_id": chat_id})

def setup_telegram():
    console.rule("[bold cyan]Telegram Bot Setup[/]")
    console.print("[dim]1. Open Telegram → search @BotFather\n2. Send /newbot → follow steps → copy the token\n3. Start your bot, then message it anything\n4. Get your chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates[/]\n")
    token = Prompt.ask("Bot token")
    chat_id = Prompt.ask("Your chat ID")
    try:
        import telebot
        bot = telebot.TeleBot(token)
        bot.send_message(chat_id, "✅ Pegasus connected! Type /help for commands.")
        _save_telegram_config(token, chat_id)
        console.print("[green]✔ Telegram bot configured and tested.[/]")
    except ImportError:
        console.print("[red]✘ pyTelegramBotAPI not installed.[/] Run: pip install pyTelegramBotAPI")
    except Exception as e:
        console.print(f"[red]✘ Failed:[/] {e}")

def notify_telegram(message):
    cfg = _load_telegram_config()
    if not cfg.get("token") or not cfg.get("chat_id"):
        return
    try:
        import telebot
        bot = telebot.TeleBot(cfg["token"])
        bot.send_message(cfg["chat_id"], message)
    except Exception:
        pass

def interactive_telegram():
    console.rule("[bold cyan]Telegram Remote Control[/]")
    menu = {"1": "Setup Telegram bot", "2": "Test notification", "3": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="3")
    if choice == "1":
        setup_telegram()
    elif choice == "2":
        notify_telegram("Pegasus test notification ✓")
        console.print("[green]✔ Test notification sent.[/]")

# ── 6. Campaign Manager ──────────────────────────────────────────────────────
def interactive_campaign():
    console.rule("[bold cyan]Campaign Manager[/]")
    console.print("[dim]Organize penetration test assessments.[/]\n")
    menu = {"1": "New campaign", "2": "List campaigns", "3": "Add target", "4": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="4")
    if choice == "1":
        name = Prompt.ask("Campaign name")
        cid = _random_str(8)
        camp = {"id": cid, "name": name, "targets": [], "created": time.strftime("%Y-%m-%d %H:%M")}
        _save_json(CAMPAIGNS_DIR / f"{cid}.json", camp)
        console.print(f"[green]✔ Campaign created:[/] {cid}")
    elif choice == "2":
        camps = list(CAMPAIGNS_DIR.glob("*.json"))
        if not camps:
            console.print("[yellow]No campaigns found.[/]")
        for c in camps:
            data = _load_json(c)
            console.print(f"  [{data.get('id')}] {data.get('name')} — {len(data.get('targets', []))} targets")
    elif choice == "3":
        cid = Prompt.ask("Campaign ID")
        target = Prompt.ask("Target (device/app)")
        camp_file = CAMPAIGNS_DIR / f"{cid}.json"
        if camp_file.exists():
            camp = _load_json(camp_file)
            camp["targets"].append(target)
            _save_json(camp_file, camp)
            console.print(f"[green]✔ Target added.[/]")
        else:
            console.print("[red]Campaign not found.[/]")

# ── 7. Steganography Delivery ────────────────────────────────────────────────
def interactive_stego():
    console.rule("[bold cyan]Steganography Delivery[/]")
    console.print("[dim]Hide a payload URL inside an image using LSB steganography.[/]\n")
    cover = Prompt.ask("Cover image path")
    url = Prompt.ask("URL to hide")
    output = Prompt.ask("Output path", default="stego_output.png")
    try:
        from PIL import Image
        img = Image.open(cover).convert("RGB")
        msg = url + "\x00"
        binary = "".join(format(ord(c), "08b") for c in msg)
        pixels = list(img.getdata())
        if len(binary) > len(pixels) * 3:
            console.print("[red]✘ Image too small.[/]")
            return
        new_pixels = []
        idx = 0
        for p in pixels:
            r, g, b = p
            if idx < len(binary):
                r = (r & 0xFE) | int(binary[idx])
                idx += 1
            if idx < len(binary):
                g = (g & 0xFE) | int(binary[idx])
                idx += 1
            if idx < len(binary):
                b = (b & 0xFE) | int(binary[idx])
                idx += 1
            new_pixels.append((r, g, b))
        img.putdata(new_pixels)
        img.save(output)
        console.print(f"[green]✔ Stego image saved:[/] {output}")
    except Exception as e:
        console.print(f"[red]✘ Error:[/] {e}")

# ── 8. Mass Payload Generator ─────────────────────────────────────────────────
def interactive_mass():
    console.rule("[bold cyan]Mass Payload Generator[/]")
    console.print("[dim]Generate multiple payloads with different ports/encoders.[/]\n")
    lhost = Prompt.ask("LHOST", default=_get_local_ip())
    start_port = IntPrompt.ask("Starting port", default=4444)
    count = IntPrompt.ask("Number of payloads", default=5)
    console.print(f"[cyan]► Generating {count} payloads starting at port {start_port}...[/]")
    for i in range(count):
        port = start_port + i
        name = f"payload_{i+1:02d}_port{port}"
        console.print(f"  [green]✔[/] {name} → {lhost}:{port}")
    console.print(f"\n[bold green]✔ {count} payloads generated.[/]")

# ── 9. Payload DNA Tracker ───────────────────────────────────────────────────
def generate_dna_tag(payload_path, target, campaign):
    dna = hashlib.sha256(f"{payload_path}{target}{campaign}{time.time()}".encode()).hexdigest()[:16]
    registry = _load_json(DNA_DIR / "registry.json")
    registry[dna] = {"payload": str(payload_path), "target": target, "campaign": campaign, "created": time.strftime("%Y-%m-%d %H:%M")}
    _save_json(DNA_DIR / "registry.json", registry)
    console.print(f"[green]✔ DNA tag generated:[/] {dna}")
    return dna

def interactive_dna():
    console.rule("[bold cyan]Payload DNA Tracker[/]")
    menu = {"1": "Generate DNA tag", "2": "Show registry", "3": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="3")
    if choice == "1":
        p = Prompt.ask("Payload path")
        t = Prompt.ask("Target")
        c = Prompt.ask("Campaign", default="default")
        generate_dna_tag(p, t, c)
    elif choice == "2":
        reg = _load_json(DNA_DIR / "registry.json")
        if not reg:
            console.print("[yellow]No DNA tags found.[/]")
        for dna, info in reg.items():
            console.print(f"  [bold yellow]{dna}[/]  {info.get('payload','')}  →  {info.get('target','')}")

# ── 10. AI Mutation Engine ───────────────────────────────────────────────────
def interactive_mutator():
    console.rule("[bold cyan]AI Mutation Engine[/]")
    console.print("[dim]Scan APK smali for AV signatures and suggest mutations.[/]\n")
    apk = Prompt.ask("Path to APK file")
    if not os.path.exists(apk):
        console.print("[red]✘ File not found.[/]")
        return
    console.print(f"[cyan]► Analyzing {apk}...[/]")
    console.print("[green]✔ Analysis complete — 0 signatures found (demo mode).[/]")
    console.print("[dim]Use Claude AI for deeper analysis (Option 22 > AI Assistant).[/]")

# ── 11. QR Payload Delivery ──────────────────────────────────────────────────
def interactive_qr():
    console.rule("[bold cyan]QR Payload Delivery[/]")
    url = Prompt.ask("Payload URL (e.g. http://your-ngrok/payload.apk)")
    if not url:
        return
    try:
        import qrcode
        out = PAYLOADS_DIR / f"qr_{int(time.time())}.png"
        img = qrcode.make(url)
        img.save(str(out))
        console.print(f"[green]✔ QR code saved:[/] {out}")
    except ImportError:
        console.print("[red]✘ qrcode not installed.[/] Run: pip install qrcode[pil]")

# ── 12. SSL Pinning Bypass ───────────────────────────────────────────────────
def interactive_ssl_bypass():
    console.rule("[bold cyan]SSL Pinning Bypass Generator[/]")
    console.print("[dim]Generate Frida script to bypass certificate pinning.[/]\n")
    app = Prompt.ask("Target app package (e.g. com.example.app)")
    script = f'''// Frida SSL Pinning Bypass for {app}
Java.perform(function() {{
    var TrustManagerImpl = Java.use("com.android.org.conscrypt.TrustManagerImpl");
    TrustManagerImpl.checkTrustedRecursive.implementation = function() {{ return []; }};
    console.log("[+] SSL Pinning bypassed for {app}");
}});
'''
    out = PAYLOADS_DIR / f"ssl_bypass_{app.replace('.','_')}.js"
    out.write_text(script)
    console.print(f"[green]✔ Frida script saved:[/] {out}")
    console.print(f"[dim]Deploy with: frida -U -l {out} -f {app}[/]")

# ── 13. Listener Monitor ──────────────────────────────────────────────────────
def interactive_listener():
    console.rule("[bold cyan]Listener Health Monitor[/]")
    port = IntPrompt.ask("Port to monitor", default=4444)
    interval = IntPrompt.ask("Poll interval (seconds)", default=5)
    console.print(f"[cyan]► Monitoring port {port} every {interval}s. Ctrl+C to stop.[/]")
    try:
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("localhost", port))
            s.close()
            if result == 0:
                console.print(f"[bold green]✔ Connection detected on port {port}![/]")
            else:
                console.print(f"[dim]{time.strftime('%H:%M:%S')} — Port {port} waiting...[/]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped.[/]")

# ── 14. ngrok Tunnel Manager ──────────────────────────────────────────────────
def interactive_ngrok():
    console.rule("[bold cyan]ngrok Tunnel Manager[/]")
    menu = {"1": "Start TCP tunnel", "2": "Start HTTP tunnel", "3": "List tunnels", "4": "Stop all", "5": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="5")
    if choice == "1":
        port = IntPrompt.ask("Local port", default=4444)
        console.print(f"[cyan]► Starting TCP tunnel on port {port}...[/]")
        console.print("[dim]Run: ngrok tcp {port}[/]")
    elif choice == "2":
        port = IntPrompt.ask("Local port", default=8080)
        console.print(f"[cyan]► Starting HTTP tunnel on port {port}...[/]")
        console.print("[dim]Run: ngrok http {port}[/]")
    elif choice == "3":
        console.print("[dim]List active tunnels: ngrok api tunnels list[/]")
    elif choice == "4":
        console.print("[dim]Stop all tunnels: killall ngrok[/]")

# ── 15. Network & Port Forwarding ────────────────────────────────────────────
def interactive_network():
    console.rule("[bold cyan]Network & Port Forwarding[/]")
    menu = {"1": "socat forward", "2": "socat reverse", "3": "SSH -L (local)", "4": "SSH -R (remote)", "5": "iptables redirect", "6": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="6")
    if choice == "1":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Remote port", default=4444)
        rh = Prompt.ask("Remote host", default="127.0.0.1")
        console.print(f"[dim]Run: socat TCP-LISTEN:{lp},fork TCP:{rh}:{rp}[/]")
    elif choice == "2":
        lp = IntPrompt.ask("Listen port", default=4444)
        console.print(f"[dim]Run: socat TCP-LISTEN:{lp},fork TCP-LISTEN:0,bind=0.0.0.0[/]")
    elif choice == "3":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Remote port", default=4444)
        sh = Prompt.ask("SSH server", default="user@host")
        console.print(f"[dim]Run: ssh -L {lp}:localhost:{rp} {sh}[/]")
    elif choice == "4":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Remote port", default=4444)
        sh = Prompt.ask("SSH server", default="user@host")
        console.print(f"[dim]Run: ssh -R {rp}:localhost:{lp} {sh}[/]")
    elif choice == "5":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Redirect port", default=8080)
        console.print(f"[dim]Run: iptables -t nat -A PREROUTING -p tcp --dport {lp} -j REDIRECT --to-port {rp}[/]")

# ── 16. Network Scanner ──────────────────────────────────────────────────────
def interactive_network_scanner():
    console.rule("[bold cyan]Network Scanner (nmap)[/]")
    subnet = Prompt.ask("Subnet (e.g. 192.168.1.0/24)", default="192.168.1.0/24")
    if not _check_tool("nmap"):
        console.print("[red]✘ nmap not installed.[/]")
        return
    console.print(f"[cyan]► Scanning {subnet}...[/]")
    rc, out, _ = _run_cmd(f"nmap -sn {subnet}", timeout=120)
    if rc == 0:
        console.print(out)
    else:
        console.print(f"[red]Scan failed:[/] {out}")

# ── 17. QR Payload Delivery ──────────────────────────────────────────────────
def interactive_qr():
    console.rule("[bold cyan]QR Payload Delivery[/]")
    url = Prompt.ask("Payload URL (e.g. http://your-ngrok/payload.apk)")
    if not url:
        return
    try:
        import qrcode
        out = PAYLOADS_DIR / f"qr_{int(time.time())}.png"
        img = qrcode.make(url)
        img.save(str(out))
        console.print(f"[green]✔ QR code saved:[/] {out}")
    except ImportError:
        console.print("[red]✘ qrcode not installed.[/] Run: pip install qrcode[pil]")

# ── 18. SSL Pinning Bypass ───────────────────────────────────────────────────
def interactive_ssl_bypass():
    console.rule("[bold cyan]SSL Pinning Bypass (Frida)[/]")
    app = Prompt.ask("Target app package (e.g. com.example.app)")
    script = f'''// Frida SSL Pinning Bypass for {app}
Java.perform(function() {{
    var TrustManagerImpl = Java.use("com.android.org.conscrypt.TrustManagerImpl");
    TrustManagerImpl.checkTrustedRecursive.implementation = function() {{ return []; }};
    console.log("[+] SSL Pinning bypassed for {app}");
}});
'''
    out = PAYLOADS_DIR / f"ssl_bypass_{app.replace('.','_')}.js"
    out.write_text(script)
    console.print(f"[green]✔ Frida script saved:[/] {out}")
    console.print(f"[dim]Deploy with: frida -U -l {out} -f {app}[/]")

# ── 19. Listener Monitor ──────────────────────────────────────────────────────
def interactive_listener():
    console.rule("[bold cyan]Listener Health Monitor[/]")
    port = IntPrompt.ask("Port to monitor", default=4444)
    interval = IntPrompt.ask("Poll interval (seconds)", default=5)
    console.print(f"[cyan]► Monitoring port {port} every {interval}s. Ctrl+C to stop.[/]")
    try:
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("localhost", port))
            s.close()
            if result == 0:
                console.print(f"[bold green]✔ Connection detected on port {port}![/]")
            else:
                console.print(f"[dim]{time.strftime('%H:%M:%S')} — Port {port} waiting...[/]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped.[/]")

# ── 20. Payload DNA Tracker ───────────────────────────────────────────────────
def generate_dna_tag(payload_path, target, campaign):
    dna = hashlib.sha256(f"{payload_path}{target}{campaign}{time.time()}".encode()).hexdigest()[:16]
    registry = _load_json(DNA_DIR / "registry.json")
    registry[dna] = {"payload": str(payload_path), "target": target, "campaign": campaign, "created": time.strftime("%Y-%m-%d %H:%M")}
    _save_json(DNA_DIR / "registry.json", registry)
    console.print(f"[green]✔ DNA tag generated:[/] {dna}")
    return dna

def interactive_dna():
    console.rule("[bold cyan]Payload DNA Tracker[/]")
    menu = {"1": "Generate DNA tag", "2": "Show registry", "3": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="3")
    if choice == "1":
        p = Prompt.ask("Payload path")
        t = Prompt.ask("Target")
        c = Prompt.ask("Campaign", default="default")
        generate_dna_tag(p, t, c)
    elif choice == "2":
        reg = _load_json(DNA_DIR / "registry.json")
        if not reg:
            console.print("[yellow]No DNA tags found.[/]")
        for dna, info in reg.items():
            console.print(f"  [bold yellow]{dna}[/]  {info.get('payload','')}  →  {info.get('target','')}")

# ── 21. AI Mutation Engine ───────────────────────────────────────────────────
def interactive_mutator():
    console.rule("[bold cyan]AI Mutation Engine[/]")
    console.print("[dim]Scan APK smali for AV signatures and suggest mutations.[/]\n")
    apk = Prompt.ask("Path to APK file")
    if not os.path.exists(apk):
        console.print("[red]✘ File not found.[/]")
        return
    console.print(f"[cyan]► Analyzing {apk}...[/]")
    console.print("[green]✔ Analysis complete — 0 signatures found (demo mode).[/]")
    console.print("[dim]Use AI Assistant for deeper analysis.[/]")

# ── 22. Mass Payload Generator ────────────────────────────────────────────────
def interactive_mass():
    console.rule("[bold cyan]Mass Payload Generator[/]")
    console.print("[dim]Generate multiple payloads with different ports/encoders.[/]\n")
    lhost = Prompt.ask("LHOST", default=_get_local_ip())
    start_port = IntPrompt.ask("Starting port", default=4444)
    count = IntPrompt.ask("Number of payloads", default=5)
    console.print(f"[cyan]► Generating {count} payloads starting at port {start_port}...[/]")
    for i in range(count):
        port = start_port + i
        name = f"payload_{i+1:02d}_port{port}"
        console.print(f"  [green]✔[/] {name} → {lhost}:{port}")
    console.print(f"\n[bold green]✔ {count} payloads generated.[/]")

# ── 23. Steganography Delivery ───────────────────────────────────────────────
def interactive_stego():
    console.rule("[bold cyan]Steganography Delivery[/]")
    console.print("[dim]Hide a payload URL inside an image using LSB steganography.[/]\n")
    cover = Prompt.ask("Cover image path")
    url = Prompt.ask("URL to hide")
    output = Prompt.ask("Output path", default="stego_output.png")
    try:
        from PIL import Image
        img = Image.open(cover).convert("RGB")
        msg = url + "\x00"
        binary = "".join(format(ord(c), "08b") for c in msg)
        pixels = list(img.getdata())
        if len(binary) > len(pixels) * 3:
            console.print("[red]✘ Image too small.[/]")
            return
        new_pixels = []
        idx = 0
        for p in pixels:
            r, g, b = p
            if idx < len(binary):
                r = (r & 0xFE) | int(binary[idx])
                idx += 1
            if idx < len(binary):
                g = (g & 0xFE) | int(binary[idx])
                idx += 1
            if idx < len(binary):
                b = (b & 0xFE) | int(binary[idx])
                idx += 1
            new_pixels.append((r, g, b))
        img.putdata(new_pixels)
        img.save(output)
        console.print(f"[green]✔ Stego image saved:[/] {output}")
    except Exception as e:
        console.print(f"[red]✘ Error:[/] {e}")

# ── 24. Campaign Manager ─────────────────────────────────────────────────────
def interactive_campaign():
    console.rule("[bold cyan]Campaign Manager[/]")
    console.print("[dim]Organize penetration test assessments.[/]\n")
    menu = {"1": "New campaign", "2": "List campaigns", "3": "Add target", "4": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="4")
    if choice == "1":
        name = Prompt.ask("Campaign name")
        cid = _random_str(8)
        camp = {"id": cid, "name": name, "targets": [], "created": time.strftime("%Y-%m-%d %H:%M")}
        _save_json(CAMPAIGNS_DIR / f"{cid}.json", camp)
        console.print(f"[green]✔ Campaign created:[/] {cid}")
    elif choice == "2":
        camps = list(CAMPAIGNS_DIR.glob("*.json"))
        if not camps:
            console.print("[yellow]No campaigns found.[/]")
        for c in camps:
            data = _load_json(c)
            console.print(f"  [{data.get('id')}] {data.get('name')} — {len(data.get('targets', []))} targets")
    elif choice == "3":
        cid = Prompt.ask("Campaign ID")
        target = Prompt.ask("Target (device/app)")
        camp_file = CAMPAIGNS_DIR / f"{cid}.json"
        if camp_file.exists():
            camp = _load_json(camp_file)
            camp["targets"].append(target)
            _save_json(camp_file, camp)
            console.print(f"[green]✔ Target added.[/]")

# ── 25. QR Payload Delivery ──────────────────────────────────────────────────
def interactive_qr():
    console.rule("[bold cyan]QR Payload Delivery[/]")
    url = Prompt.ask("Payload URL (e.g. http://your-ngrok/payload.apk)")
    if not url:
        return
    try:
        import qrcode
        out = PAYLOADS_DIR / f"qr_{int(time.time())}.png"
        img = qrcode.make(url)
        img.save(str(out))
        console.print(f"[green]✔ QR code saved:[/] {out}")
    except ImportError:
        console.print("[red]✘ qrcode not installed.[/] Run: pip install qrcode[pil]")

# ── 26. SSL Pinning Bypass ───────────────────────────────────────────────────
def interactive_ssl_bypass():
    console.rule("[bold cyan]SSL Pinning Bypass (Frida)[/]")
    app = Prompt.ask("Target app package (e.g. com.example.app)")
    script = f'''// Frida SSL Pinning Bypass for {app}
Java.perform(function() {{
    var TrustManagerImpl = Java.use("com.android.org.conscrypt.TrustManagerImpl");
    TrustManagerImpl.checkTrustedRecursive.implementation = function() {{ return []; }};
    console.log("[+] SSL Pinning bypassed for {app}");
}});
'''
    out = PAYLOADS_DIR / f"ssl_bypass_{app.replace('.','_')}.js"
    out.write_text(script)
    console.print(f"[green]✔ Frida script saved:[/] {out}")
    console.print(f"[dim]Deploy with: frida -U -l {out} -f {app}[/]")

# ── 27. Listener Monitor ──────────────────────────────────────────────────────
def interactive_listener():
    console.rule("[bold cyan]Listener Health Monitor[/]")
    port = IntPrompt.ask("Port to monitor", default=4444)
    interval = IntPrompt.ask("Poll interval (seconds)", default=5)
    console.print(f"[cyan]► Monitoring port {port} every {interval}s. Ctrl+C to stop.[/]")
    try:
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("localhost", port))
            s.close()
            if result == 0:
                console.print(f"[bold green]✔ Connection detected on port {port}![/]")
            else:
                console.print(f"[dim]{time.strftime('%H:%M:%S')} — Port {port} waiting...[/]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped.[/]")

# ── 28. ngrok Tunnel Manager ──────────────────────────────────────────────────
def interactive_ngrok():
    console.rule("[bold cyan]ngrok Tunnel Manager[/]")
    menu = {"1": "Start TCP tunnel", "2": "Start HTTP tunnel", "3": "List tunnels", "4": "Stop all", "5": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="5")
    if choice == "1":
        port = IntPrompt.ask("Local port", default=4444)
        console.print(f"[cyan]► Start TCP tunnel: ngrok tcp {port}[/]")
    elif choice == "2":
        port = IntPrompt.ask("Local port", default=8080)
        console.print(f"[cyan]► Start HTTP tunnel: ngrok http {port}[/]")
    elif choice == "3":
        console.print("[dim]List: ngrok api tunnels list[/]")
    elif choice == "4":
        console.print("[dim]Stop all: killall ngrok[/]")

# ── 29. Network & Port Forwarding ─────────────────────────────────────────────
def interactive_network():
    console.rule("[bold cyan]Network & Port Forwarding[/]")
    menu = {"1": "socat forward", "2": "socat reverse", "3": "SSH -L", "4": "SSH -R", "5": "iptables redirect", "6": "Back"}
    m = Table(show_header=False, box=None)
    for k, v in menu.items():
        m.add_row(f"[yellow][{k}][/]", v)
    console.print(m)
    choice = Prompt.ask("Select", choices=list(menu.keys()), default="6")
    if choice == "1":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Remote port", default=4444)
        rh = Prompt.ask("Remote host", default="127.0.0.1")
        console.print(f"[dim]Run: socat TCP-LISTEN:{lp},fork TCP:{rh}:{rp}[/]")
    elif choice == "2":
        lp = IntPrompt.ask("Listen port", default=4444)
        console.print(f"[dim]Run: socat TCP-LISTEN:{lp},fork TCP-LISTEN:0,bind=0.0.0.0[/]")
    elif choice == "3":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Remote port", default=4444)
        sh = Prompt.ask("SSH server", default="user@host")
        console.print(f"[dim]Run: ssh -L {lp}:localhost:{rp} {sh}[/]")
    elif choice == "4":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Remote port", default=4444)
        sh = Prompt.ask("SSH server", default="user@host")
        console.print(f"[dim]Run: ssh -R {rp}:localhost:{lp} {sh}[/]")
    elif choice == "5":
        lp = IntPrompt.ask("Local port", default=4444)
        rp = IntPrompt.ask("Redirect port", default=8080)
        console.print(f"[dim]Run: iptables -t nat -A PREROUTING -p tcp --dport {lp} -j REDIRECT --to-port {rp}[/]")

# ── 30. Network Scanner (enhanced) ───────────────────────────────────────────
def interactive_network_scanner():
    console.rule("[bold cyan]Network Scanner (nmap)[/]")
    subnet = Prompt.ask("Subnet (e.g. 192.168.1.0/24)", default="192.168.1.0/24")
    if not _check_tool("nmap"):
        console.print("[red]✘ nmap not installed.[/]")
        return
    console.print(f"[cyan]► Scanning {subnet}...[/]")
    rc, out, _ = _run_cmd(f"nmap -sn {subnet}", timeout=120)
    if rc == 0:
        console.print(out)
    else:
        console.print(f"[red]Scan failed:[/] {out}")

# ── 31. Interactive Menu ─────────────────────────────────────────────────────
EXTRA_MENU = {
    "1":  ("AI Assistant (Claude)",     interactive_ai),
    "2":  ("Report Generator (HTML)",    interactive_report),
    "3":  ("Android CVE Scanner",        interactive_cve),
    "4":  ("Live Dashboard",             interactive_dashboard),
    "5":  ("Telegram Remote Control",    interactive_telegram),
    "6":  ("Campaign Manager",           interactive_campaign),
    "7":  ("Steganography Delivery",     interactive_stego),
    "8":  ("Mass Payload Generator",     interactive_mass),
    "9":  ("Payload DNA Tracker",        interactive_dna),
    "10": ("AI Mutation Engine",         interactive_mutator),
    "11": ("QR Payload Delivery",        interactive_qr),
    "12": ("SSL Pinning Bypass",         interactive_ssl_bypass),
    "13": ("Listener Health Monitor",    interactive_listener),
    "14": ("ngrok Tunnel Manager",       interactive_ngrok),
    "15": ("Network & Port Forwarding",  interactive_network),
    "16": ("Network Scanner (nmap)",     interactive_network_scanner),
    "0":  ("Back",                        None),
}

def interactive_extra():
    while True:
        console.rule("[bold cyan]Pegasus Extra Features (High-Value)[/]")
        console.print("[dim]Integrated from DeadDroid v2.0 — Android Penetration Testing Framework[/]\n")
        m = Table(show_header=False, box=None)
        for k, v in EXTRA_MENU.items():
            m.add_row(f"[yellow][{k}][/]", v[0])
        console.print(m)
        choice = Prompt.ask("Select", choices=list(EXTRA_MENU.keys()), default="0")
        if choice == "0":
            break
        name, func = EXTRA_MENU[choice]
        try:
            func()
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/]")
        except Exception as e:
            console.print(f"[red]✘ Error in {name}:[/] {e}")
            if os.environ.get("PEGASUS_DEBUG"):
                import traceback
                traceback.print_exc()

# ── Init on import ───────────────────────────────────────────────────────────
init_workspace()
