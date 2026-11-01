"""Tool schema rules. Runs at boot; a failure is a startup error."""
from . import grammar

MAX_OPTIONAL, MAX_PROPS = 6, 24


def lint(schema: dict) -> list[str]:
    errs = []
    if schema.get("type") != "object":
        errs.append("root must be object")
    if schema.get("additionalProperties") is not False:
        errs.append("must close object")
    props = schema.get("properties", {})
    if len(props) > MAX_PROPS:
        errs.append(f"{len(props)} props > {MAX_PROPS}")
    optional = [k for k in props if k not in schema.get("required", [])]
    if len(optional) > MAX_OPTIONAL:
        errs.append(f"{len(optional)} optional > {MAX_OPTIONAL}")
    for key, spec in props.items():
        if "enum" in spec and not spec["enum"]:
            errs.append(f"{key}: empty enum")
        if len(spec.get("description", "")) > 120:
            errs.append(f"{key}: description > 120")
        if spec.get("type") == "object":
            errs.append(f"{key}: nested object unsupported")
    try:
        grammar.gbnf(schema)
    except ValueError as exc:
        errs.append(str(exc))
    return errs
