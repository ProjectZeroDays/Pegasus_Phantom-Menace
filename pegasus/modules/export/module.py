"""
Export module - HTML assessment report generation.

Generates self-contained HTML assessment reports from device fingerprints,
scan results, findings, and operator notes. Reports include:
- Executive summary
- Device inventory table
- Vulnerability findings with severity badges
- Exploit / payload deployment log
- Recommendations
- Appendix with raw evidence

All output is written to the reports directory. No external services.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import HookType
from pegasus.core.config import get_settings

try:
    import logging, colorama.ansitowin32 as _cw
    _orig = _cw.write
    def _safe(s, *a, **k):
        try: return _orig(s, *a, **k)
        except OSError: return len(s)
    _cw.write = _safe
    _oe = logging.StreamHandler.emit
    def _se(self, record):
        try: return _oe(self, record)
        except OSError: pass
    logging.StreamHandler.emit = _se
except Exception:
    pass


SEVERITY_COLORS = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "medium": "#ca8a04",
    "low": "#16a34a",
    "info": "#2563eb",
}


class ExportModule(BaseModule):
    """HTML assessment report generation."""

    @property
    def module_name(self) -> str:
        return "Report Export"

    @property
    def module_description(self) -> str:
        return "HTML assessment report generation"

    @property
    def module_category(self) -> str:
        return "exploit"

    async def _register_commands(self) -> None:
        self.register_command("export-html", "Generate HTML assessment report", self.cmd_html)
        self.register_command("export-json", "Export findings as JSON", self.cmd_json)
        self.register_command("export-markdown", "Generate Markdown assessment report", self.cmd_markdown)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="export_dashboard",
            component_type="panel",
            path="/export",
            title="Report Export",
            icon="📄",
            order=12,
        )

    async def _register_hooks(self) -> None:
        pass

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_html(self, *args) -> None:
        """Generate an HTML assessment report."""
        title = self.prompt("Report title", default="Pegasus Assessment Report") or "Pegasus Assessment Report"
        author = self.prompt("Author", default="ProjectZeroDays") or "ProjectZeroDays"
        device = self.prompt("Target device (serial/model)", default="Unknown") or "Unknown"
        findings_raw = self.prompt("Findings (JSON array or semicolon-separated 'sev|title|desc')", default="[]")
        findings = self._parse_findings(findings_raw)
        out = self._write_html(title, author, device, findings)
        self.print_success(f"HTML report saved: {out}")

    async def cmd_json(self, *args) -> None:
        """Export findings as JSON."""
        findings_raw = self.prompt("Findings (JSON array or semicolon-separated 'sev|title|desc')", default="[]")
        findings = self._parse_findings(findings_raw)
        out_dir = Path(self.context.get_reports_dir())
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"assessment_{datetime.now():%Y%m%d_%H%M%S}.json"
        out.write_text(json.dumps(findings, indent=2), encoding="utf-8")
        self.print_success(f"JSON report saved: {out}")

    async def cmd_markdown(self, *args) -> None:
        """Generate a Markdown assessment report."""
        title = self.prompt("Report title", default="Pegasus Assessment Report") or "Pegasus Assessment Report"
        device = self.prompt("Target device", default="Unknown") or "Unknown"
        findings_raw = self.prompt("Findings (JSON array or semicolon-separated 'sev|title|desc')", default="[]")
        findings = self._parse_findings(findings_raw)
        out = self._write_markdown(title, device, findings)
        self.print_success(f"Markdown report saved: {out}")

    # ── Helpers ────────────────────────────────────────────────────────

    def _parse_findings(self, raw: str) -> List[Dict[str, str]]:
        raw = (raw or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    return [f if isinstance(f, dict) else {"severity": "info", "title": str(f), "description": ""} for f in data]
            except json.JSONDecodeError:
                pass
        findings = []
        for part in raw.split(";"):
            part = part.strip()
            if not part:
                continue
            bits = [b.strip() for b in part.split("|")]
            findings.append({
                "severity": bits[0] if bits else "info",
                "title": bits[1] if len(bits) > 1 else part,
                "description": bits[2] if len(bits) > 2 else "",
            })
        return findings

    def _severity_color(self, sev: str) -> str:
        return SEVERITY_COLORS.get((sev or "").lower(), "#6b7280")

    def _write_html(self, title: str, author: str, device: str, findings: List[Dict[str, str]]) -> Path:
        out_dir = Path(self.context.get_reports_dir())
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"assessment_{datetime.now():%Y%m%d_%H%M%S}.html"
        rows = []
        for f in findings:
            sev = (f.get("severity") or "info").lower()
            color = self._severity_color(sev)
            rows.append(
                f'<tr><td><span class="badge" style="background:{color}">{html.escape(sev.upper())}</span></td>'
                f'<td>{html.escape(f.get("title", ""))}</td>'
                f'<td>{html.escape(f.get("description", ""))}</td></tr>'
            )
        if not rows:
            rows.append('<tr><td colspan="3" class="empty">No findings recorded</td></tr>')
        doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f0c; color: #e6f2ea; }}
header {{ padding: 24px 32px; background: #101613; border-bottom: 1px solid #1d2a22; }}
header h1 {{ margin: 0 0 6px; font-size: 22px; }}
header .meta {{ color: #7fa88e; font-size: 13px; }}
main {{ padding: 24px 32px; max-width: 1100px; }}
section {{ margin-bottom: 28px; }}
section h2 {{ font-size: 16px; color: #9fe8c0; border-bottom: 1px solid #1d2a22; padding-bottom: 6px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #1d2a22; vertical-align: top; }}
th {{ color: #9fe8c0; font-weight: 600; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; color: #fff; font-size: 11px; font-weight: 600; }}
.empty {{ color: #7fa88e; font-style: italic; }}
.kv {{ display: grid; grid-template-columns: 180px 1fr; gap: 4px 16px; font-size: 13px; }}
.kv dt {{ color: #7fa88e; }}
.kv dd {{ margin: 0; }}
footer {{ padding: 16px 32px; color: #5a7a66; font-size: 12px; border-top: 1px solid #1d2a22; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="meta">Author: {html.escape(author)} &middot; Generated: {datetime.now(timezone.utc).isoformat()} &middot; Target: {html.escape(device)}</div>
</header>
<main>
  <section>
    <h2>Executive Summary</h2>
    <p>This report documents the findings of an authorized security assessment performed with Pegasus Phantom Menace. {len(findings)} finding(s) were recorded.</p>
  </section>
  <section>
    <h2>Target</h2>
    <dl class="kv">
      <dt>Device</dt><dd>{html.escape(device)}</dd>
      <dt>Report date</dt><dd>{datetime.now(timezone.utc).isoformat()}</dd>
      <dt>Author</dt><dd>{html.escape(author)}</dd>
    </dl>
  </section>
  <section>
    <h2>Findings</h2>
    <table>
      <thead><tr><th>Severity</th><th>Title</th><th>Description</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
  <section>
    <h2>Recommendations</h2>
    <ul>
      <li>Prioritize critical and high severity findings for immediate remediation.</li>
      <li>Apply vendor patches where available; verify patch levels against the affected ranges.</li>
      <li>Re-assess after remediation to confirm closure.</li>
    </ul>
  </section>
</main>
<footer>Pegasus Phantom Menace &middot; Authorized security assessment &middot; Handle per your organization's responsible disclosure policy.</footer>
</body>
</html>
"""
        out.write_text(doc, encoding="utf-8")
        return out

    def _write_markdown(self, title: str, device: str, findings: List[Dict[str, str]]) -> Path:
        out_dir = Path(self.context.get_reports_dir())
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"assessment_{datetime.now():%Y%m%d_%H%M%S}.md"
        lines = [
            f"# {title}",
            "",
            f"- **Target:** {device}",
            f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Findings",
            "",
        ]
        if not findings:
            lines.append("_No findings recorded._")
        for f in findings:
            lines.append(f"### [{f.get('severity', 'info').upper()}] {f.get('title', '')}")
            lines.append("")
            if f.get("description"):
                lines.append(f["description"])
                lines.append("")
        lines.extend([
            "## Recommendations",
            "",
            "1. Prioritize critical and high severity findings.",
            "2. Apply vendor patches where available.",
            "3. Re-assess after remediation.",
            "",
        ])
        out.write_text("\n".join(lines), encoding="utf-8")
        return out


__all__ = ["ExportModule"]
