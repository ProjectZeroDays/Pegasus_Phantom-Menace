install:
	pip install -e .

apply:
	python scripts/apply_bundle.py bundle.txt . 



smoke:
	bash scripts/smoke.sh 

docs/HANDOFF.md: docs/PLAN.md
	python3 scripts/handoff.py

.PHONY: handoff handoff-check handoff-guard agents agents-check agents-lint hooks hooks-check bootstrap-check plan-lint ready-check blocked gate module-new preflight doctor
handoff: docs/HANDOFF.md
handoff-guard: handoff-check
	@test -s docs/HANDOFF.md || { echo "HANDOFF empty"; exit 1; }

# >>> pegasus bootstrap managed targets (regenerated) >>>
PHASE ?= P0
VENV ?= .venv
PY ?= python3
BLAST ?= readonly
COST ?= cheap

docs/HANDOFF.md: docs/PLAN.md
	python3 scripts/handoff.py

.PHONY: setup test integ contract lint ui parity dist import openapi-snapshot
.PHONY: verify version-check map plan-lint require ready-check blocked gate
.PHONY: module-new preflight doctor bootstrap-check agents agents-check agents-lint
.PHONY: hooks hooks-check handoff handoff-check handoff-guard modules-lint audit
.PHONY: audit-check caps-matrix caps-consistency caps-baseline risk-lint noplatform
.PHONY: capability-check conformance replay evidence-check eval

setup: hooks
	python3 -m venv $(VENV)
	$(VENV)/bin/python -m pip install -U pip
	@if [ -f pyproject.toml ]; then $(VENV)/bin/pip install -e ".[all]"; \
	 else $(VENV)/bin/pip install -e "pegasus[dev]"; fi

test:
	$(PY) -m pytest -q pegasus/tests/unit pegasus/tests/py
integ:
	$(PY) -m pytest -q pegasus/tests/integ -m "not live"
contract:
	$(PY) -m pytest -q pegasus/tests/contract
lint:
	$(PY) -m ruff check . && $(PY) -m mypy --strict pegasus
ui:
	npm run --prefix pegasus/ui/web build
parity:
	$(PY) scripts/parity.py
dist:
	bash packaging/build_all_formats.sh
import:
	$(PY) -c "import pegasus, pegasus.modules.base"
openapi-snapshot:
	$(PY) scripts/openapi_snapshot.py
verify:
	python3 scripts/verify.py --doctor
version-check:
	$(PY) scripts/version_check.py
modules-lint:
	$(PY) scripts/modules_lint.py
audit:
	$(PY) scripts/audit_derive.py
audit-check:
	$(PY) scripts/audit_derive.py --check
caps-matrix:
	$(PY) scripts/caps_matrix.py
caps-consistency:
	$(PY) scripts/caps_consistency.py
caps-baseline:
	@rm -f build/caps_baseline.json
	@$(PY) scripts/caps_matrix.py >/dev/null || true
	@test -s build/caps_baseline.json || { echo "baseline not written"; exit 1; }
	@echo "baseline refreshed"
risk-lint:
	$(PY) scripts/risk_lint.py
noplatform:
	$(PY) scripts/no_platform_branch.py
capability-check:
	$(PY) scripts/capability_check.py
conformance:
	$(PY) -m pytest -q pegasus/tests/conformance
replay:
	$(PY) -m pytest -q pegasus/tests/transcripts
evidence-check:
	$(PY) -m pytest -q pegasus/tests/contract -k evidence
eval:
	$(PY) -m pytest -q pegasus/tests/eval
map:
	@test -s build/map.diff || { echo "G11 FAIL: build/map.diff missing or empty"; exit 1; }
	@if grep -n 'UNKNOWN' build/map.diff; then echo "G11 FAIL: unresolved rows above"; exit 1; fi
	@echo "G11 PASS"
plan-lint:
	python3 scripts/require.py --lint
require:
	python3 scripts/require.py "$(PHASE)"
ready-check:
	python3 scripts/verify.py --ready
blocked:
	python3 scripts/verify.py --blocked
gate:
	python3 scripts/verify.py --gate "$(GATE)"
module-new:
	$(PY) scripts/module_new.py "$(ID)" --blast=$(BLAST) --cost=$(COST)
preflight:
	python3 scripts/verify.py --preflight
doctor: hooks-check bootstrap-check
	python3 scripts/verify.py --doctor
bootstrap-check:
	python3 scripts/bootstrap-check.py
agents:
	python3 scripts/emit_agents.py
agents-check:
	python3 scripts/emit_agents.py --check
agents-lint:
	$(PY) -m pytest -q pegasus/tests/contract/test_agents.py
hooks:
	git config core.hooksPath .githooks && chmod +x .githooks/* || true
hooks-check:
	@test "$$(git config core.hooksPath || true)" = ".githooks" || { echo "hooksPath unset — run make hooks"; exit 1; }
	@for f in .githooks/pre-commit .githooks/pre-push .githooks/commit-msg; do \
	  test -x "$$f" || { echo "$$f missing or not executable"; exit 1; }; done
handoff: docs/HANDOFF.md
handoff-check:
	python3 scripts/handoff.py --check
handoff-guard: handoff-check
	@test -s docs/HANDOFF.md || { echo "HANDOFF empty"; exit 1; }
# <<< pegasus bootstrap managed targets <<<
