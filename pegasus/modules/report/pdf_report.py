"""Engagement report: phase summary, per-host hashes, gaps."""
import hashlib
import pathlib
import time

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..autonomous import journal


def build(run_id: str, out: pathlib.Path, operator: str = "operator") -> pathlib.Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out), pagesize=A4, topMargin=18 * mm,
                            bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    flow = [Paragraph("Pegasus -- Engagement Report", styles["Title"]),
            Paragraph(f"Run {run_id} Â· {operator} Â· "
                      f"{time.strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
            Spacer(1, 8 * mm)]

    events = journal.replay(run_id)
    phases: dict[str, int] = {}
    for event in events:
        phases[event["phase"]] = phases.get(event["phase"], 0) + 1
    table = Table([["Phase", "Events"]] + [[k, str(v)] for k, v in phases.items()],
                  colWidths=[90 * mm, 30 * mm])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, (0.7, 0.7, 0.7))]))
    flow += [Paragraph("Phase summary", styles["Heading2"]), table, Spacer(1, 6 * mm)]

    flow.append(Paragraph("Evidence", styles["Heading2"]))
    root = pathlib.Path.home() / ".pegasus" / "runs" / run_id / "loot"
    if root.exists():
        for host_dir in sorted(root.iterdir()):
            if not host_dir.is_dir():
                continue
            flow.append(Paragraph(f"Host {host_dir.name}", styles["Heading3"]))
            for artifact in sorted(host_dir.iterdir()):
                if artifact.name == "manifest.json":
                    continue
                digest = hashlib.sha256(artifact.read_bytes()).hexdigest()[:24]
                flow.append(Paragraph(f"<font size=8>{artifact.name} Â· "
                                      f"sha256 {digest}--¦</font>", styles["Normal"]))

    gaps = [e["message"] for e in events if e["message"].startswith("fail ")]
    flow += [Spacer(1, 6 * mm), Paragraph("Gaps", styles["Heading2"])]
    for gap in gaps[:80] or ["none recorded"]:
        flow.append(Paragraph(f"<font size=8>{gap}</font>", styles["Normal"]))

    flow += [Spacer(1, 6 * mm), Paragraph("Method", styles["Heading2"]),
             Paragraph("Generated from the run journal. Reliability ratings are "
                       "heuristic; manual review required before delivery.",
                       styles["Normal"])]
    doc.build(flow)
    return out
