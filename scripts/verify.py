"""Route and unit checks. Run on every PR."""
import sys

sys.path.insert(0, ".")

from pegasus.modules.ai import grammar, qbrain, schemas, validator  # noqa: E402
from pegasus.modules.parity import matrix  # noqa: E402

CHECKS = [
    ("open schema fails", lambda: _raises(lambda: grammar.gbnf({"type": "object"}))),
    ("mutated rejected", lambda: not validator.validate('{"cmd":"x"}', schemas.SHELL)[0]),
    ("prose rejected", lambda: not validator.validate("Sure!", schemas.SHELL)[0]),
    ("qbrain answers", lambda: "command" in qbrain.fallback("planner", "dump sms")["text"]),
    ("parity 13 vectors", lambda: matrix._count_vectors() == 13),
    ("parity postex >= 9", lambda: matrix._count_postex() >= 9),
]


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except Exception:
        return True


def main() -> int:
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = bool(fn())
        except Exception as exc:
            ok = False
            print(f"  {name}: raised {exc}")
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
        failures += 0 if ok else 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
