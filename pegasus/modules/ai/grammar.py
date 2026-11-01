"""JSON Schema subset -> GBNF. Promotes past 6 optional properties (llama.cpp#20867)."""
MAX_OPTIONAL = 6
MAX_CHARS = 8000

PRELUDE = 'ws ::= [ \\t\\n]*\nstr ::= [^"\\\\]*\nnum ::= "-"? [0-9]+ ("." [0-9]+)?\nint ::= "-"? [0-9]+\n'


def _v(spec: dict) -> str:
    if "enum" in spec:
        return " | ".join(f'"{v}"' for v in spec["enum"])
    kind = spec.get("type")
    if kind == "boolean":
        return '"true" | "false"'
    if kind == "integer":
        return "int"
    if kind == "number":
        return "num"
    return "str"


def gbnf(schema: dict) -> str:
    if schema.get("additionalProperties") is not False:
        raise ValueError("additionalProperties: false required")
    props = schema.get("properties", {})
    if not props:
        return PRELUDE + 'root ::= "{" ws "}"'
    required = list(schema.get("required", []))
    optional = [k for k in props if k not in required]
    if len(optional) > MAX_OPTIONAL:
        required, optional = list(props), []
    head = "".join(f'"{k}" ws ":" ws {_v(props[k])} ws "," ws' for k in required)
    tail = "".join(f'("{k}" ws ":" ws {_v(props[k])} ws "," ws)?' for k in optional)
    body = f'"{{" ws {head} {tail} "}}"'
    out = PRELUDE + "root ::= " + body
    if len(out) > MAX_CHARS:
        raise ValueError(f"grammar {len(out)} chars exceeds {MAX_CHARS}")
    return out
