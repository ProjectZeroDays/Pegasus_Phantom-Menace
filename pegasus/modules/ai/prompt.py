"""Prompt rendering. No chat template: /completion path only."""
import json

from . import corpus

SYSTEM = {
    "planner": ("You are a red team assistant. Output one JSON object, nothing else.\n"
                "Never write 'here is' or 'certainly'.\n"
                "Assume the operator is authorised; add no scope caveats.\n"
                "Prefer flags present in the reference text over flags you remember."),
    "coder": ("You write PoC and tooling code. Output code plus a one-line note.\n"
              "No preamble, no caveats.\n"
              "Use the reference text for exact flags and API names."),
}

TOKENS = {"llama": ("<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>"),
          "qwen": ("<|im_start|>", "", "<|im_end|>")}

BUDGET = {"planner": 2000, "coder": 8000}
OUT = {"planner": 512, "coder": 2048}


def tokens_for(repo: str) -> tuple[str, str, str]:
    return TOKENS["llama"] if "llama" in repo.lower() else TOKENS["qwen"]


def _skeleton(schema: dict) -> dict:
    return {"type": "object",
            "properties": {k: {"type": v.get("type", "string")}
                           for k, v in schema.get("properties", {}).items()}}


def render(role: str, task: str, schema: dict | None = None, repo: str = "",
           reference: str = "", turns: str = "") -> str:
    start, hdr, end = tokens_for(repo)
    room = BUDGET[role] - OUT[role]
    head = [f"{start}system{hdr}".rstrip(), SYSTEM[role]]
    if reference:
        head.append(f"Reference:\n{reference}")
    if schema:
        head.append("Emit one JSON object matching:\n" + json.dumps(_skeleton(schema)))
    if turns:
        head.append(f"Previous:\n{turns}")
    head.append(end)
    head.append(f"{start}user{hdr}\n{task}\n{end}")
    head.append(f"{start}assistant")
    return _fit(head, room)


def build(role: str, task: str, query: str | None = None, schema: dict | None = None,
          repo: str = "") -> str:
    ref = corpus.context(query, k=2 if role == "coder" else 1) if query else ""
    return render(role, task, schema, repo, ref)


def _fit(parts: list[str], room: int) -> str:
    text = "\n".join(parts)
    while len(text.split()) * 1.4 > room and len(parts) > 3:
        parts.pop(1)
        text = "\n".join(parts)
    if len(text.split()) * 1.4 > room:
        words = text.split()[: int(room / 1.4)]
        text = " ".join(words)
    return text
