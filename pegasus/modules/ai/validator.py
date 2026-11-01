"""Two-stage validation: JSON, then schema, then shell parse."""
import json
import shlex

from jsonschema import Draft202012Validator


def validate(text: str, schema: dict) -> tuple[bool, str]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"json: {exc.msg} at {exc.pos}"
    errs = list(Draft202012Validator(schema).iter_errors(obj))
    if errs:
        return False, f"schema: {errs[0].message}"
    for key, spec in schema.get("properties", {}).items():
        if spec.get("format") == "shell" and isinstance(obj.get(key), str):
            try:
                shlex.split(obj[key])
            except ValueError as exc:
                return False, f"shell: {exc}"
    return True, ""
