"""
Merged Workflow Registry -- Q-ANDROID INFEROR + Pegasus Phantom Menace
/finish /swarm /all /auto /never-ask /improve
"""
from pathlib import Path

WORKFLOWS = {
    "frp-unlock": {"sources": ["9_complete.py", "pegasus/modules/access_workflow/module.py"], "status": "merged"},
    "payload-gen": {"sources": ["9_complete.py", "pegasus/modules/payload/module.py"], "status": "merged"},
    "payload-mutate": {"sources": ["9_complete.py", "pegasus/modules/payload/module.py"], "status": "merged"},
    "payload-dna": {"sources": ["9_complete.py (crypto)", "pegasus/modules/payload/module.py"], "status": "merged"},
    "fingerprint": {"sources": ["9_complete.py (AdbLocator)", "pegasus/ui/web/backend/app.py"], "status": "merged"},
    "harvest": {"sources": ["9_complete.py (ContentHarvester)", "pegasus/ui/web/backend/app.py"], "status": "merged"},
    "access-autonomous": {"sources": ["9_complete.py (FrpRecovery/TcpTransport)", "pegasus/modules/access_workflow/module.py"], "status": "merged"},
    "sessions": {"sources": ["9_complete.py (AdbModule)", "pegasus/ui/web/backend/app.py"], "status": "merged"},
    "crypto_selftest": {"sources": ["9_complete.py"], "status": "available"},
    "menu": {"sources": ["9_complete.py"], "status": "styled (PEGASUS blue/green)"},
}

MERGED_FILE = Path(__file__).parent / "merged_workflows.md"
