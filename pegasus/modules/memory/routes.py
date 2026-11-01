"""Memory routes."""
from flask import request

from . import blocks, consolidate, db, decay, extract, recall, store_episode


def register(app, ok, fail):
    @app.get("/api/memory/blocks")
    def mem_blocks():
        return ok(blocks.all_blocks(request.args.get("case", "")))

    @app.put("/api/memory/blocks/<name>")
    def mem_block_write(name):
        body = request.get_json(silent=True) or {}
        blocks.write(name, body.get("case", ""), body.get("body", ""))
        return ok({"name": name})

    @app.get("/api/memory/facts")
    def mem_facts():
        con = db.db()
        rows = con.execute("SELECT id, key, value, confidence, valid_to FROM fact"
                           " WHERE (? = '' OR source LIKE ?) ORDER BY id DESC LIMIT 200",
                           (request.args.get("case", ""),
                            f"%{request.args.get('case', '')}%")).fetchall()
        return ok({"facts": [dict(zip(("id", "key", "value", "confidence", "valid_to"), r))
                             for r in rows]})

    @app.delete("/api/memory/facts/<int:fact_id>")
    def mem_fact_delete(fact_id):
        con = db.db()
        con.execute("DELETE FROM fact WHERE id=?", (fact_id,))
        con.commit()
        return ok({"deleted": fact_id})

    @app.post("/api/memory/recall")
    def mem_recall():
        body = request.get_json(silent=True) or {}
        return ok({"context": recall.recall(body.get("query", ""),
                                            body.get("case", ""),
                                            body.get("budget", 900))})

    @app.post("/api/memory/sweep")
    def mem_sweep():
        return ok(decay.sweep())

    @app.post("/api/memory/commit")
    def mem_commit():
        body = request.get_json(silent=True) or {}
        cands = extract.candidates(body.get("run_id", ""), body.get("text", ""),
                                   body.get("verdict", ""), body.get("case"))
        return ok({"committed": consolidate.commit(cands)})
