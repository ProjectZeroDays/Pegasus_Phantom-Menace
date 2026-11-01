"""Parity route."""
from . import matrix


def register(app, ok, fail):
    @app.get("/api/parity")
    def parity_report():
        return ok(matrix.report())
