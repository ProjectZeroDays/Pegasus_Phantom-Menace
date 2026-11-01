"""DPO pairs from near-miss traces: same prompt, one right, one wrong."""
from . import db


def pairs(role: str, limit: int = 2000) -> list[dict]:
    out = []
    for bad in db.rows("SELECT prompt, response FROM trace WHERE role=? AND"
                       " verdict LIKE 'schema:%' LIMIT ?", (str(role), limit)):
        good = db.rows("SELECT response FROM trace WHERE role=? AND verdict='pass'"
                       " AND prompt=? LIMIT 1", (str(role), bad["prompt"]))
        if good:
            out.append({"prompt": bad["prompt"], "chosen": good[0]["response"],
                        "rejected": bad["response"]})
    return out
