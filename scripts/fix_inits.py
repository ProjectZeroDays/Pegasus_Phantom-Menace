"""Rewrite the package __init__ files that re-export their module's routes.

Run as a script: ``python scripts/fix_inits.py``. Importing this module must not
touch the working tree.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INITS = {
    "pegasus/modules/relay/__init__.py": "from . import relay_routes\n",
    "pegasus/modules/report/__init__.py": "from . import report_routes\n",
    "pegasus/modules/parity/__init__.py": "from . import parity_routes, matrix\n",
    "pegasus/modules/tenant/__init__.py": "from . import tenant_routes, scope\n",
    "pegasus/modules/memory/__init__.py": (
        "from . import routes, db, embed, extract, recall, consolidate, decay, "
        "blocks, store_episode\n"),
    "pegasus/modules/exploits/__init__.py": "from . import registry, chain\n",
    "pegasus/modules/crypto/__init__.py": "from . import atrest\n",
    "pegasus/modules/antiforensics/__init__.py": "from . import wipe\n",
    "pegasus/modules/alerts/__init__.py": "from . import webhooks\n",
    "pegasus/modules/ota/__init__.py": "from . import update\n",
}


def main() -> int:
    for rel, content in INITS.items():
        path = ROOT / rel
        path.write_text('"""Module."""\n' + content, encoding="utf-8")
        print("Fixed", rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
