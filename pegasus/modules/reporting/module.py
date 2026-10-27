"""
Pegasus Phantom Menace v2 - Reporting Module
HTML, PDF, JSON report generation with findings and payload tracking.
"""
from __future__ import annotations

import jinja2
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel

from pegasus_v2.modules.base import BaseModule
from pegasus_v2.core.plugin import CommandInfo, UIComponent, hook, command, ui_component, HookType
from pegasus_v2.core.config import get_settings


class ReportingModule(BaseModule):
    """Report generation module - HTML, PDF, JSON reports."""

    @property
    def module_name(self) -> str:
        return "Report Generator"

    @property
    def module_description(self) -> str:
        return "Professional HTML/PDF/JSON pentest reports with findings and payload tracking"

    @property
    def module_category(self) -> str:
        return "reporting"

    async def _register_commands(self) -> None:
        self.register_command("report-gen", "Generate pentest report", self.cmd_report_gen)
        self.register_command("report-list", "List generated reports", self.cmd_report_list)
        self.register_command("report-view", "View report in browser", self.cmd_report_view)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="report_dashboard",
            component_type="panel",
            path="/reports",
            title="Reports",
            icon="📝",
            order=5,
        )

    async def _register_hooks(self) -> None:
        self.register_hook(HookType.REPORT_GENERATED, self._on_report_generated, priority=10)

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_report_gen(self, *args) -> None:
        """Generate a pentest report."""
        self._console.print("[cyan]► Report Generator[/cyan]\n")

        title = self.prompt("Report title", default="Android Security Assessment")
        tester = self.prompt("Tester name", default="Security Team")
        target = self.prompt("Target (device/app)")
        summary = self.prompt("Executive summary")
        recommendations = self.prompt("Recommendations")

        # Collect findings
        findings = []
        while self.confirm("Add a finding?", default=True):
            finding = {
                "title": self.prompt("Finding title"),
                "severity": self.prompt("Severity", choices=["Critical","High","Medium","Low","Info"], default="High"),
                "description": self.prompt("Description"),
                "impact": self.prompt("Impact"),
                "evidence": self.prompt("Evidence / PoC"),
                "recommendation": self.prompt("Recommendation"),
            }
            findings.append(finding)

        # Collect payloads
        payloads = []
        while self.confirm("Add payload record?", default=False):
            payloads.append({
                "name": self.prompt("Payload name"),
                "type": self.prompt("Payload type"),
                "lhost": self.prompt("LHOST"),
                "lport": self.prompt("LPORT"),
                "notes": self.prompt("Notes"),
            })

        # Generate report
        settings = self.context.settings
        reports_dir = self.context.get_reports_dir()
        now = time.strftime("%Y-%m-%d %H:%M UTC")
        filename = f"report_{title.replace(' ', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.html"
        out_path = reports_dir / filename

        html = self._build_html_report(
            title=title, tester=tester, target=target, summary=summary,
            findings=findings, payloads=payloads, recommendations=recommendations,
            now=now,
        )

        out_path.write_text(html, encoding="utf-8")
        self.print_success(f"Report saved: {out_path}")
        self._console.print(f"\n[bold]Open in browser:[/bold] file://{out_path.resolve()}")

        await self.hooks.execute(HookType.REPORT_GENERATED, {
            "report": str(out_path),
            "title": title,
            "findings_count": len(findings),
        })

    async def cmd_report_list(self, *args) -> None:
        """List generated reports."""
        reports_dir = self.context.get_reports_dir()
        reports = list(reports_dir.glob("*.html"))

        if not reports:
            self.print_warning("No reports found")
            return

        table = Table(title="Generated Reports", header_style="bold cyan")
        table.add_column("Filename", style="bold yellow")
        table.add_column("Size", style="dim")
        table.add_column("Created", style="green")

        for r in sorted(reports, key=lambda p: p.stat().st_mtime, reverse=True):
            size = r.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / 1024 / 1024:.1f} MB"
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.stat().st_mtime))
            table.add_row(r.name, size_str, mtime)

        self._console.print(table)

    async def cmd_report_view(self, *args) -> None:
        """View report in browser."""
        reports_dir = self.context.get_reports_dir()
        reports = list(reports_dir.glob("*.html"))

        if not reports:
            self.print_warning("No reports found")
            return

        # Show list and let user pick
        for i, r in enumerate(sorted(reports, key=lambda p: p.stat().st_mtime, reverse=True), 1):
            self._console.print(f"  [{i}] {r.name}")

        choice = self.prompt("Select report to view", choices=[str(i) for i in range(1, len(reports)+1)], default="1")
        report = sorted(reports, key=lambda p: p.stat().st_mtime, reverse=True)[int(choice)-1]

        import webbrowser
        webbrowser.open(str(report.resolve()))
        self.print_success(f"Opened: {report.name}")

    # ── Report HTML Template ──────────────────────────────────────────

    def _build_html_report(self, title: str, tester: str, target: str,
                           summary: str, findings: List[Dict],
                           payloads: List[Dict], recommendations: str,
                           now: str) -> str:
        """Build HTML report from template."""
        findings_html = ""
        for f in findings:
            sev_lower = f.get("severity", "info").lower()
            sev = f.get("severity", "INFO").upper()
            findings_html += f"""
            <div class="finding">
              <span class="badge badge-{sev_lower}">{sev}</span>
              <h3>{f.get('title', 'Untitled')}</h3>
              <p><strong>Description:</strong> {f.get('description', '')}</p>
              <p><strong>Impact:</strong> {f.get('impact', '')}</p>
              <p><strong>Evidence:</strong></p>
              <pre><code>{f.get('evidence', '').replace('<', '&lt;').replace('>', '&gt;')}</code></pre>
              <p><strong>Recommendation:</strong> {f.get('recommendation', '')}</p>
            </div>
            """

        payloads_html = ""
        if payloads:
            rows = ""
            for p in payloads:
                rows += f"<tr><td>{p.get('name','')}</td><td>{p.get('type','')}</td><td>{p.get('lhost','')}:{p.get('lport','')}</td><td>{p.get('notes','')}</td></tr>"
            payloads_html = f"""
            <table>
              <tr><th>File</th><th>Type</th><th>LHOST:LPORT</th><th>Notes</th></tr>
              {rows}
            </table>
            """
        else:
            payloads_html = "<p>No payloads recorded.</p>"

        template = f"""<!DOCTYPE html>
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
  <p style="margin-top:8px;color:#8b949e">Generated: {now} &nbsp;|&nbsp; Tester: {tester} &nbsp;|&nbsp; Target: {target}</p>
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
      <tr><td>Test Type</td><td>Black Box</td></tr>
      <tr><td>Authorization</td><td>Written authorization obtained</td></tr>
      <tr><td>Start Date</td><td>{now}</td></tr>
      <tr><td>End Date</td><td>{now}</td></tr>
      <tr><td>Tools Used</td><td>Pegasus, ADB</td></tr>
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
        return template

    # ── Hook Handlers ─────────────────────────────────────────────────

    async def _on_report_generated(self, context) -> None:
        self.print_info(f"Report generated: {context.data.get('report', 'unknown')}")