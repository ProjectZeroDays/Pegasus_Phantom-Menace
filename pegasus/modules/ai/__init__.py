"""Model layer. Schema lint runs at import and aborts the process on failure."""
from . import grammar, schema_lint, schemas, routes, model_routes


def load_schemas() -> dict[str, str]:
    compiled = {}
    for name, schema in schemas.REGISTRY.items():
        errs = schema_lint.lint(schema)
        if errs:
            raise RuntimeError(f"schema {name}: {'; '.join(errs)}")
        compiled[name] = grammar.gbnf(schema)
    return compiled
