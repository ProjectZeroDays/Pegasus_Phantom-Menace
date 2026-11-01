"""Mine rejected enum values. Candidates only, never auto-applied."""
from collections import Counter

from . import db


def mine(schema_name: str) -> list[str]:
    rows = db.rows("SELECT response FROM trace WHERE verdict LIKE 'schema:%'"
                   " AND prompt LIKE ?", (f"%{schema_name}%",))
    counts = Counter()
    for row in rows:
        for token in row["response"].replace(",", " ").split():
            token = token.strip('":{}[]')
            if 2 < len(token) < 24 and token.islower():
                counts[token] += 1
    return [v for v, n in counts.most_common(20) if n >= 3]
