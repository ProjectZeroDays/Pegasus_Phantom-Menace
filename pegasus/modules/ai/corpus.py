"""FTS5 corpus over --help output and module manifests."""
import pathlib
import re
import shutil
import sqlite3
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB = pathlib.Path.home() / ".pegasus" / "corpus.db"
BINS = ["nmap", "adb", "am", "pm", "content", "dumpsys", "getevent", "su",
        "sqlite3", "openssl", "hashcat", "curl", "ssh", "smbclient"]


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
                "kind, binary, body, tokenize='porter')")
    return con


def _index(con, kind: str, binary: str, body: str) -> int:
    if len(body) < 20:
        return 0
    con.execute("INSERT INTO docs(kind, binary, body) VALUES(?,?,?)",
                (kind, binary, body[:20000]))
    return 1


def harvest() -> int:
    con, rows = _db(), 0
    for name in BINS:
        path = shutil.which(name)
        if not path:
            continue
        try:
            out = subprocess.run([path, "--help"], capture_output=True, text=True,
                                 timeout=10).stdout
        except subprocess.TimeoutExpired:
            continue
        rows += _index(con, "help", name, out)
    for manifest in (ROOT / "post_exploitation" / "manifests").glob("*.yaml"):
        rows += _index(con, "module", manifest.stem, manifest.read_text())
    con.commit()
    return rows


def _fts(query: str) -> str:
    terms = re.findall(r"[a-z0-9_-]{2,}", query.lower())[:8]
    return " OR ".join(f'"{t}"' for t in terms)


def context(query: str, k: int = 8) -> str:
    con = _db()
    try:
        rows = con.execute("SELECT binary, body FROM docs WHERE docs MATCH ? "
                           "ORDER BY rank LIMIT ?", (_fts(query), k)).fetchall()
    except sqlite3.OperationalError:
        return ""
    return "\n---\n".join(f"[{b}]\n{t}" for b, t in rows)
