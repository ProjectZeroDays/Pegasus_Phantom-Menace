# PEGASUS: PHANTOM MENACE — MASTER BLUEPRINT
### v19.0 — the four rules as method

**File:** `docs/BLUEPRINT.md`
**Supersedes:** v18.0. Conflicts resolve here.
**Change:** the four load-bearing rules move from ADR-only into the methodology — PR template, review checklist, definition of ready, QA rubric, drill script, migration, onboarding. New PART XVIII. Nothing removed.

---

# THE ONE PAGE

**What.** Android-first collection platform. Multi-OS transport broker, gated engagement lifecycle, validation pipeline where nothing reaches a target without four deterministic checks, two adversarially paired models, a human signature, and a VM pass.

**The five things that make it defensible**

1. The workflow is a state machine — no collection before an authorization hash. *(§9)*
2. Every capability carries a signed expiring certificate or is refused. *(§6)*
3. Every gate checker must prove it denies a known-bad case. *(§5)*
4. The verification primitives verify each other. *(§12)*
5. Abort preserves evidence; tidy-up deletes it. *(§13)*

**The four rules that are method, not just code**

- **A checker without a deny-case is not a checker.** PR template field, review gate, `gate-coverage`. *(§112)*
- **Only `force` skips adjacency, and it journals why.** Reviewers reject any other skip. *(§113)*
- **An uncited claim is `unknown`, not `false`.** Applies to judge output and to review comments. *(§114)*
- **Abort preserves; tidy-up deletes.** Scored in every drill. *(§115)*

**The five things that will kill it**

1. A checker that always returns yes — invisible without §5 and §112.
2. Canary negatives written from imagination instead of real crashes.
3. A stale pin. Swapping a model mid-contract voids every prior verdict.
4. Treating `PARTIAL` as success.
5. Building breadth before the primitives. 170 modules on a bad gate is 170 lies.

**Cost.** 415 engineer-days. Defensible at day 95, sellable to one client under NDA. Generally sellable at 235. Government-ready at 415.

**Cannot do.** Live zero-click chains, baseband, SS7.

**Stop rule.** If R1 passes 120 days, stop and cut scope.

---

## 0. Reading contract

| Rule | Enforced by | Method layer |
|---|---|---|
| Capability truth (`documented`/`inferred`/`emulated`) | lint | PR field §112 |
| Only `validated` fires | machine guard | review §113 |
| Nothing unverified, ungated, unaudited | state guard, resolver, journal | review §113 |
| No action outside its stage; no stage skip | `stage` gate, adjacency guard | review §113 |
| No claim without a signed certificate | `Cert.__post_init__` | PR field §112 |
| No checker without a deny-case | `register()` positional | PR field, review gate §112 |
| No pack without a live refresh date | `Pack.__init__` | PR field §112 |
| No verdict without a live pin | `judge.judge()` | review §114 |
| No silent degradation | single `Health` writer | review §113 |
| No report on unverified custody | `report` gate | review §113 |
| Abort preserves evidence | `abort()` | drill rubric §115 |

ADRs Appendix E. Sections `§n`.

---

# PART I — GROUND

## 1. Current state

**Real:** 17 intent channels · 66 structure-verified carriers · 5-step ADB chain · 28-command factory · 32 pages · SQLite auth with passkey and USDC verification.

**Theatre:**

| Claim | Reality |
|---|---|
| "30 NSO parity 100%" | category checklist; no selection, no gate, no offsets |
| "100% implemented" | paths exist; several are one-line wrappers |
| "zero-click" | zero *target* interaction, zero remote reach |
| "macOS/Linux" | source-only code, Windows packaging |
| "AES-256-GCM" | XOR in the delivery path |
| "NSO-class" | parity of nouns |

### 1.1 Database fails to start — four causes

1. `setup_init.py` connects before `PEGASUS_HOME` exists
2. `~/.pegasus/` inherits umask; daemon and CLI diverge to different users
3. `journal_mode=WAL` on a network or synced home stalls on the lock file
4. No single-instance guard; two launches race, the loser exits silently, the UI loads against a dead store

```python
# services/store.py
def init(home: Path) -> Engine:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    fh = open(home / ".lock", "w"); fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    eng = create_engine(f"sqlite:///{home/'pegasus.db'}", connect_args={"timeout": 15})
    with eng.begin() as c:
        c.exec_driver_sql("PRAGMA journal_mode=DELETE" if is_network_fs(home) else "PRAGMA journal_mode=WAL")
        c.exec_driver_sql("PRAGMA foreign_keys=ON"); c.exec_driver_sql("PRAGMA synchronous=NORMAL")
    migrate(eng)
    return eng
```

`GET /health` reports `{db, migrations, wal, instance}`. Startup refuses with a readable message.

*All four, not one. Fixing only the mkdir leaves the network-WAL stall and the double-launch race.*

### 1.2 Delivery misconfigurations

| # | Issue | Fix | Gate |
|---|---|---|---|
| 1 | server binds loopback | bind `0.0.0.0`, advertise egress IP | `server_reachable` |
| 2 | no MIME on staged files | per-medium MIME table | `mime_registered` |
| 3 | fixed 1.6 s `auto_send` | composer-ready + 400 ms | `intent_resolves` |
| 4 | no size ceiling | encoder asserts | `size_within_ceiling` |
| 5 | no shortener | short token path | `url_wellformed` |
| 6 | no receipts | per-medium receipt path | — |
| 7 | A11+ package visibility | `<queries>` per package | `intent_resolves` |
| 8 | no read grant | content URI + `FLAG_GRANT_READ_URI_PERMISSION` | `uri_grantable` |
| 9 | cleartext blocked A9+ | HTTPS or `usesCleartextTraffic` | `cleartext_policy` |
| 10 | localhost from container | detect egress IP | `server_reachable` |

1, 2, 7, and 8 account for most "built but nothing happened."

## 2. Invariants

1. No fire without `validated` state, matching fingerprint, passing medium check.
2. No carrier for a medium the exploit cannot survive.
3. No crypto claim without a wire-uniqueness proof.
4. No control enabled for a state the device is not in.
5. No destructive control without a generated undo or explicit `irreversible` ack.
6. No promotion without four oracle checks, judge, auditor, human signature, VM pass.
7. No module without contract test and replay fixture.
8. No percentage that cannot be derived.
9. Capabilities, not platforms. Leases, not sequencing.
10. `PARTIAL` is a result. Silence is a bug.
11. Meter before lease. No orphaned spend.
12. Every artifact hashed, signed, attributed.
13. No verdict without a live pin.
14. No medium without a decoder.
15. No `reversible` claim without a live certificate.
16. No infection without a lawful basis.
17. Gates fail closed.
18. Certificates revoke on first production failure.
19. Every checker has a deny-case and an admit-case in CI.
20. Every pack carries a `refresh_by` date.
21. Every certificate is signed and verified on read.
22. Degradation is named, never silent.
23. A case advances one stage at a time.
24. No collection before authorization; no report before custody verification.
25. A stalled case is handled, not abandoned.
26. Only `force` skips adjacency, and it journals why.
27. Uncited claims become `unknown`, not `false`.
28. The auditor never sees confidence.
29. A rule that is only in code is half a rule — it also gets a review gate.

## 3. Architecture

```
CASE SPINE  intake → authorization → scoping → fingerprint → plan → infect
            → establish → collect → exploit-deepen → report → review → close
              ↑ recovery at every stage · handover preserves stage and cursors

     every action gated by (stage, state, caps, trust, role)
                          ▼
┌──────── PRIMITIVES ────────┐  ┌──── GOVERNANCE ────┐
│ gate (canary-required)     │  │ device pool ·      │
│ canary (expiring)          │  │ worker split ·     │
│ certify (signed)           │  │ canary budget      │
│ Health (single writer)     │  └────────────────────┘
└──────────┬─────────────────┘
┌──────────▼─────────┐  ┌──────────────────────┐
│ CONTROL + ARB      │  │ EVIDENCE             │
│ resolver · WFQ     │  │ journal · custody    │
│ claims · undo      │  │ admissibility·redact │
└──────────┬─────────┘  └──────────────────────┘
┌──────────▼─────────────────────────────────┐
│ DATA · fingerprint → select → gate → build │
│ → seal → encode → send · VALIDATION · VM   │
└──────────┬─────────────────────────────────┘
┌──────────▼─────────────────────────────────┐
│ TRANSPORT BROKER (23 transports)            │
└────────────────────────────────────────────┘
```

## 4. Repository

```
pegasus/
├── verify/{gate,canary,certify,health,bootstrap,budget,selfcheck}.py
├── verify/gates/  verify/canaries/
├── case/{machine,stage,board,intake,auth,scope,recover,handover,stale,close}.py
├── control/{registry,resolve,schedule,claims,undo,dryrun,verify,journal,rollback}.py
├── pipeline/{machine,bundle,dedupe,judge,pin,auditor,human_gate,route,invalidate,vm,device,budget,metrics,observe}.py
├── pipeline/oracle/{1_release,2_control,3_reachable,4_deterministic}.py
├── delivery/{media,format,decoder,codec,matrix,envelope,budget,pipeline,gate,receipts,taxonomy}/
├── fingerprint/{hlr,preview,silent,channel,adb,signals,confidence,cell}.py
├── arsenal/{state,index,select,feeds,scaffold,promote,platforms,rank}.py
├── fuzz/{corpus,mutate,triage,dedupe,offsets,runner,table,harness,repro,chaos}.py
├── exploit_catalog/<platform>/<cve>/{manifest.yaml,validator.py,payload/,offsets.json,harness/,decoders.yaml}
├── post_exploitation/{module,registry,manifests,preflight,spec}.py
├── core/{caps,host,transport,session,broker,lease,drift,trust}.py
├── transports/{adb,agent_rpc,idevice,idevice_bridge,ssh,smb,wmi,proto,radio,airplay,dlna}.py
├── c2/{inbound_listener,pairing,vps,local,revoke}.py
├── infra/{patn,white_services,noc,abuse_rules,close_circle}.py
├── evidence/{custody,anchor,hold,retention,admissible,redact,compart}.py
├── commercial/{org,workspace,entitlements,quota,meter,invoice,sla,onboarding}.py
├── compliance/{dsar,dpa,basis,export_control,licence_census}.py
├── govern/{pool,workers,quota}.py
├── services/{store,connect_watcher,pull_scheduler,delta,export,installer}.py
├── seed/{canaries,corpus,decoders}/
├── migrations/
├── .github/{PULL_REQUEST_TEMPLATE.md,REVIEW_CHECKLIST.md}
├── api/routes/{capability,control,delivery,format,fingerprint,cell,fuzz,pipeline,post_exploit,export,devices,settings,billing,compliance,verify,case,recover,govern}
├── web/src/pages/{Capability,Delivery,Formats,Fuzzer,Pipeline,PostExploit,Devices,Investigate,Billing,Settings,Compliance,VerifyHealth,CaseBoard,Intake,Authorization,Report,Review,Recover,Handover,Cost}
└── docs/{BLUEPRINT,caps,media,formats,fuzz,control,evidence,compliance,runbook,harness-guide,onboarding,adr/}
```

`Dashboard.tsx` → `Capability.tsx`; `/dashboard` 302s for one release.

---

# PART II — PRIMITIVES

## 5. `verify/gate.py`

```python
"""Admission gates. A domain cannot register without a deny/admit canary pair."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from . import health, metrics, store

@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str = ""
    unlock: str = ""
    def __bool__(self) -> bool: return self.ok
    @classmethod
    def yes(cls) -> "Verdict": return cls(True)
    @classmethod
    def no(cls, reason: str, unlock: str = "") -> "Verdict": return cls(False, reason, unlock)

Checker = Callable[[Any, Any], Verdict]
DOMAINS: dict[str, tuple[Checker, dict[str, Any]]] = {}

class GateError(Exception): pass

def register(domain: str, canary: dict[str, Any]) -> Callable[[Checker], Checker]:
    """The pair is enforced here rather than in review: a domain without a
    known-bad case is indistinguishable from a checker that always says yes."""
    if set(canary) != {"deny", "admit"}:
        raise GateError(f"{domain}: canary must be exactly deny+admit, got {set(canary)}")
    def deco(fn: Checker) -> Checker:
        DOMAINS[domain] = (fn, canary)
        return fn
    return deco

def admit(domain: str, subject: Any, ctx: Any = None) -> Verdict:
    """Fail closed. Unknown domain denies. A raising checker denies and degrades."""
    entry = DOMAINS.get(domain)
    if entry is None:
        metrics.inc("gate_no_checker", domain=domain)
        return Verdict.no("no_checker")
    checker, _ = entry
    try:
        v = checker(subject, ctx)
    except Exception as exc:
        health.degrade(f"gate:{domain}", f"checker raised: {exc!r}")
        metrics.inc("gate_checker_raised", domain=domain)
        return Verdict.no(f"checker_raised:{exc!r}")
    metrics.inc("gate_admit" if v.ok else "gate_deny", domain=domain)
    if not v.ok:
        store.denial(domain, repr(subject), v.reason)
    return v

def prove(domain: str) -> dict[str, bool]:
    """CI: a domain that admits its deny-case fails."""
    checker, canary = DOMAINS[domain]
    return {"denies": not checker(canary["deny"], None).ok,
            "admits": checker(canary["admit"], None).ok}
```

### 5.1 Domains

| Domain | Denies when | Dark state |
|---|---|---|
| `format` | no validated decoder reachable via an admitted medium | `format_dark` |
| `medium` | no codec, no receipt path, or reaches no decoder | `medium_dark` |
| `model` | no live pin or canary below threshold | `pin_dead` |
| `control` | uncertified undo on a `reversible` control | `undo_unproven` |
| `harness` | no reachability test or non-reproducible build | `harness_dark` |
| `module` | T1/T2 manifest with no method | `module_dark` |
| `decoder` | no harness or harness canary below threshold | `decoder_dark` |
| `cert` | unsigned, expired, revoked, evidence mutated | `cert_dead` |
| `stage` | action outside the current stage | `stage_dark` |
| `delivery` | any of twelve pre-send checks | `delivery_dark` |

### 5.2 Tests

```python
def test_register_rejects_partial_canary():
    with pytest.raises(GateError): register("demo", {"deny": 1})

def test_unknown_domain_denies():
    assert not admit("nope", object()).ok

def test_checker_raise_denies_and_degrades():
    register("boom", {"deny": 1, "admit": 2})(lambda s, c: 1 / 0)
    v = admit("boom", object())
    assert not v.ok and "checker_raised" in v.reason
    assert health.state("gate:boom") is health.Health.DEGRADED

def test_always_yes_checker_fails_prove():
    register("lazy", {"deny": 1, "admit": 2})(lambda s, c: Verdict.yes())
    assert not prove("lazy")["denies"]

def test_denial_is_recorded():
    register("d", {"deny": 1, "admit": 2})(lambda s, c: Verdict.no("x"))
    admit("d", "subj")
    assert store.last_denial("d").subject == "'subj'"
```

## 6. `verify/certify.py`

```python
TTL = {"reversible": 30, "deterministic": 30, "reachable": 30, "delivers": 14, "decodes": 30}

class CertError(Exception): pass
class UnsignedCert(CertError): pass
class UnknownClaim(CertError): pass

@dataclass(frozen=True)
class Cert:
    id: str
    claim: str
    subject: str
    ctx: dict
    evidence_sha: str
    at: datetime
    expires: datetime
    sig: str = ""
    def __post_init__(self) -> None:
        if self.claim not in TTL: raise UnknownClaim(self.claim)
        if not self.sig: raise UnsignedCert(f"{self.id}: no signature")
        if not keys.verify(_canon(self.body()), self.sig):
            raise UnsignedCert(f"{self.id}: signature invalid")
    def body(self) -> dict:
        d = asdict(self); d.pop("sig"); return d
    def live(self) -> bool: return self.expires > _now()

def issue(claim: str, subject: str, ctx: dict, evidence: bytes) -> Cert:
    body = {"claim": claim, "subject": subject, "ctx": ctx,
            "evidence_sha": sha256(evidence).hexdigest(),
            "at": _now(), "expires": _now() + timedelta(days=TTL[claim])}
    cert = Cert(id=new_id(), sig=keys.sign(_canon(body)), **body)
    store.put_cert(cert); journal.record("cert_issued", cert.id, claim, subject)
    return cert

def live(claim: str, subject: str, ctx: dict) -> bool:
    c = store.latest_cert(claim, subject, ctx)
    if c is None or c.revoked or not c.live(): return False
    if store.evidence_sha(c) != c.evidence_sha:
        health.degrade(f"cert:{c.id}", "evidence mutated"); return False
    return True

def revoke(claim: str, subject: str, ctx: dict, reason: str) -> None:
    """Called on the first production failure. No grace period."""
    c = store.latest_cert(claim, subject, ctx)
    if c is None: return
    store.revoke_cert(c.id, reason)
    journal.record("cert_revoked", c.id, claim, subject, reason)
    health.degrade(f"cert:{c.id}", reason)
```

### 6.1 Tests

```python
def test_cert_cannot_be_constructed_unsigned():
    with pytest.raises(UnsignedCert):
        Cert(id="x", claim="reversible", subject="s", ctx={}, evidence_sha="0",
             at=now(), expires=now() + days(1), sig="")

def test_tampered_body_fails_construction():
    c = issue("reversible", "s", {}, b"ev")
    with pytest.raises(UnsignedCert):
        Cert(**{**asdict(c), "subject": "other"})

def test_first_failure_revokes():
    issue("reversible", "s", {}, b"ev")
    assert live("reversible", "s", {})
    revoke("reversible", "s", {}, "undo failed")
    assert not live("reversible", "s", {})

def test_evidence_mutation_kills_liveness():
    issue("decodes", "s", {}, b"ev")
    store.set_evidence("decodes", "s", b"different")
    assert not live("decodes", "s", {})
```

## 7. `verify/canary.py`

```python
class PackExpired(Exception): pass
class PackTooSmall(Exception): pass

@dataclass(frozen=True)
class Pack:
    id: str
    version: int
    refresh_by: date
    min_size: int
    cases: tuple
    def __post_init__(self) -> None:
        if date.today() > self.refresh_by:
            raise PackExpired(f"{self.id} expired {self.refresh_by}")
        if len(self.cases) < self.min_size:
            raise PackTooSmall(f"{self.id}: {len(self.cases)} < {self.min_size}")

def healthy(pack_id: str, subject: str, threshold: dict) -> bool:
    s = store.latest_canary(pack_id, subject)
    if s is None or s["pack_version"] != store.pack_version(pack_id):
        return False   # edited pack with inherited history is a fresh lie
    return all(s[k] >= v for k, v in threshold.items())
```

| Pack | Subject | Size | Threshold |
|---|---|---|---|
| `judge` | model pin | 40 (20 tp / 12 tn / 8 adversarial) | tp ≥ .85, tn ≥ .85 |
| `auditor` | model pin | 30 (15 upheld / 10 overturned / 5 passive-trap) | upheld ≥ .80, overturn ≥ .70 |
| `transport` | transport | conformance suite | all pass |
| `harness` | harness | reachability + determinism ×3 | all pass |
| `decoder` | decoder | decode fixture + entry reachable | all pass |
| `undo` | control | forward → undo → original ×5 | ≥ .90 |
| `gate` | synthetic domain | deny, admit, raise | all pass |

## 8. `verify/health.py`

```python
class Health(str, Enum):
    OK = "ok"; DEGRADED = "degraded"; BLOCKED = "blocked"

def set(subsystem: str, state: Health, reason: str = "") -> None:
    store.put_health(subsystem, state.value, reason)
    banners.publish(subsystem, state.value, reason)

def degrade(s: str, reason: str) -> None: set(s, Health.DEGRADED, reason)
def block(s: str, reason: str) -> None: set(s, Health.BLOCKED, reason)
```

| Failure | State |
|---|---|
| gate registry unreadable | BLOCKED — no sends |
| canary runner down | DEGRADED — no admissions, pins hold to TTL |
| cert store unreadable | BLOCKED — read-only survives |
| pack expired | DEGRADED — domain dark, banner names the pack |

## 9. `case/machine.py`

```python
STAGES = ("intake", "authorization", "scoping", "fingerprint", "plan", "infect",
          "establish", "collect", "exploit-deepen", "report", "review", "close")

REQUIRED = {"authorization": ("basis", "auth_sha", "auth_expires", "dpa_sha"),
            "establish": ("receipt_or_hello",),
            "report": ("custody_verified",),
            "review": ("report_bundle",)}

class TransitionError(Exception): pass
class NotAdjacent(TransitionError): pass
class MissingArtifacts(TransitionError): pass
class RoleTooLow(TransitionError): pass

def advance(case, to: str, ctx) -> None:
    if to != next_stage(case.stage):
        raise NotAdjacent(f"{case.stage} -> {to}")
    v = gate.admit("stage", f"enter:{to}", ctx)
    if not v.ok: raise TransitionError(f"gate: {v.reason}")
    missing = [f for f in REQUIRED.get(to, ()) if not artifacts.present(case, f)]
    if missing: raise MissingArtifacts(", ".join(missing))
    if ctx.role < ROLE_FLOOR[to]: raise RoleTooLow(f"{to} needs role {ROLE_FLOOR[to]}")
    journal.record("stage", case.id, case.stage, to, ctx.actor)   # signed, before the write
    case.stage = to

def regress(case, to: str, ctx, reason: str) -> None:
    if STAGES.index(to) > STAGES.index(case.stage):
        raise NotAdjacent(f"regress to {to} from {case.stage}")
    journal.record("stage_regress", case.id, case.stage, to, ctx.actor, reason)
    case.stage = to
```

### 9.1 Stage gate

```python
ALLOWED = {
  "intake": {"case.edit", "target.add"},
  "authorization": {"case.edit", "target.add", "auth.record"},
  "scoping": {"scope.edit", "fingerprint.run", "abuse.check"},
  "fingerprint": {"fingerprint.run", "plan.build"},
  "plan": {"plan.build", "infect.send", "plan.approve"},
  "infect": {"infect.send", "delivery.send"},
  "establish": {"control.run:read", "control.run:write"},
  "collect": {"control.run:read", "control.run:write", "export.run"},
  "exploit-deepen": {"control.run:*", "post_exploit.run", "lateral.run"},
  "report": {"report.build", "export.run", "redact.run"},
  "review": {"review.sign", "report.amend"},
  "close": {"case.close", "hold.release"},
}

@register("stage", {"deny": "case.close", "admit": "case.edit"})
def _(action: str, ctx) -> Verdict:
    if action.startswith("enter:"):
        return Verdict.yes()
    return Verdict.yes() if action in ALLOWED.get(ctx.stage, set()) \
        else Verdict.no("stage", f"not allowed in {ctx.stage}")
```

### 9.2 Stage entry, exit, abort

| Stage | Entry gate | Artifacts | Role | Abort to |
|---|---|---|---|---|
| intake | — | targets, client contact | analyst | — |
| authorization | basis set | auth hash, DPA hash, validity window | operator | intake |
| scoping | auth hash | scope, abuse caps, exclusions | operator | authorization |
| fingerprint | scope locked | confidence, contradiction log | operator | scoping |
| plan | confidence ≥ threshold | ranked candidates, medium each | supervisor | fingerprint |
| infect | plan approved | receipts, gate results | operator | plan |
| establish | `server_hit` or agent hello | sessions, cap probe | operator | infect |
| collect | establish artifacts | passive set, pull cursors | operator | establish |
| exploit-deepen | collection baseline | post-ex, lateral, priv-esc | supervisor | collect |
| report | custody verified | bundle, gap disclosure | operator | collect |
| review | bundle present | note, amendments, sign-off | supervisor | report |
| close | review signed | final pack, retention, hold release | supervisor | review |

### 9.3 Tests

```python
def test_skip_rejected(case, ctx):
    with pytest.raises(NotAdjacent): advance(case, "collect", ctx)

def test_collect_without_auth_hash_rejected(case, ctx):
    with pytest.raises(MissingArtifacts):
        for s in ("authorization", "scoping", "fingerprint", "plan", "infect", "establish"):
            advance(case, s, ctx)

def test_regress_journalled(case, ctx):
    advance(case, "authorization", ctx); advance(case, "scoping", ctx)
    regress(case, "authorization", ctx, "scope wrong")
    assert journal.last("stage_regress").reason == "scope wrong"
```

## 10. Authorization stage

| Required | Mechanism |
|---|---|
| Lawful basis | enum: `contract` / `consent` / `legitimate` / `statutory` / `court_order` |
| Authorization document | PDF or scan, sha256 stored, signer named |
| DPA | signed copy hash; `dpa_missing` blocks |
| Validity window | start and end; expiry drops the case to read-only |
| Target identifiers | must appear in the authorization text; mismatch flags |

A case missing any of the five cannot leave the stage. Typing identifiers by hand reintroduces the failure this stage exists to prevent, so the UI extracts them from the pasted document and asks the operator to confirm.

## 11. Report and review

`report` requires custody verification for every artifact in the bundle and blocks naming the offender. Review is a different human — compared on `actor` against the signer. Self-review only below a configurable artifact count, marked `self_reviewed: true`.

## 12. Mutual verification

- `gate` has a `gate` pack: must deny, admit, and raise.
- `canary` requires a `cert` for each pack, inside `refresh_by`.
- `certify` has a `cert` gate domain: unsigned or expired denies.
- All three run in a dedicated P0 CI job. Failure blocks merge.

## 13. Recovery

```yaml
stale: { stage_idle_h: 72, auth_expiry_warn_d: 7, host_silent_h: 48 }
```

| Condition | Action |
|---|---|
| Host silent 48 h | mark `lost`, pause pull, keep artifacts |
| All hosts lost | drop to `collect` with banner, no auto-regress |
| Auth expired | read-only until renewal |
| Agent dead, path alive | requeue deploy at `establish` |

```python
def abort(case, ctx, preserve: bool = True):
    for claim in claims.by_case(case.id): claims.release(claim)
    if preserve:
        store.put_preservation(case.id, ctx.actor, ran=ran_log(case),
                               held=held_ids(case), incomplete=incomplete(case))
    journal.record("abort", case.id, ctx.actor, preserve)
    case.stage = "review"
```

**Abort never rolls back collection.** A failed case's data is still evidence, and the instinct to tidy up deletes the only thing that survived.

```python
def handover(case, to_actor, ctx):
    if ctx.role < ROLE_FLOOR[case.stage]: raise RoleTooLow(case.stage)
    journal.record("handover", case.id, ctx.actor, to_actor)
    claims.release_all(case.id)          # re-taken by the new owner
    case.owner = to_actor
    notify(to_actor, brief(case))        # generated, not remembered
```

### 13.1 Drill script

`docs/runbook/drill.md`, run monthly by a different engineer than the one who wrote the recovery code:

```
1. Start case A, collect for 4 min, kill the agent mid-pull.
   ASSERT: host -> lost, pull paused, every existing artifact still readable.
2. Start case B, advance to collect, expire the auth via clock shift.
   ASSERT: case -> read-only, banner names expiry, no control runs.
3. Start case C, advance to establish, handover to a second operator.
   ASSERT: stage unchanged, cursors unchanged, claims re-taken, brief non-empty.
4. Start case D, collect, `abort --preserve`.
   ASSERT: preservation record has ran/held/incomplete all non-empty,
           every artifact hash still matches its custody record.
5. Score each against §115. Any assertion failure is P1.
```

Step 4 is the one that catches the tidy-up instinct: an abort that deletes or seals-away partials passes a shallow check and fails the hash comparison.

## 14. Global governance

```python
class GlobalGovern:
    def take_device(self, case, host):
        """Weighted queue: supervisor > operator, then oldest case. Position visible."""
    def worker_budget(self, case):
        """Even split, floor of one, ceiling of eight total."""
    def canary_budget(self):
        """Global. A case cannot spend the platform's allowance."""
```

Per-host claims stop two controls colliding. This stops two cases fighting over five handsets.

## 15. CLI

```
pegasus case new|list|show|advance|abort|handover|close
pegasus auth record --basis contract --doc auth.pdf --expires 2027-03-01
pegasus scope set --cidr 10.0.0.0/24 --exclude 10.0.0.9
pegasus fp run|plan build|infect send|collect start
pegasus ctl run|plan <control> --host <h>
pegasus export <host> <artifact> --fmt csv
pegasus report build|review sign
pegasus verify health|admit <domain> <subject>|prove <domain>
pegasus govern queue|cost show
```

`--json` throughout. Same resolver and gate path as the UI.

---

# PART III — CONTROL PATH

## 16. Resolver

```python
class Denied(Exception):
    def __init__(self, v): super().__init__(v.reason); self.verdict = v

def resolve(c: Control, ctx: Ctx) -> Verdict:
    v = gate.admit("stage", c.action, ctx)              # 1 legal now?
    if not v.ok: return v
    v = gate.admit("control", c, ctx)                   # 2 control admissible?
    if not v.ok: return v
    if ctx.role < c.role:              return Verdict.no("role", role_name(c.role))
    if ctx.state < c.requires_state:   return Verdict.no("state", f"needs {c.requires_state}")
    if ctx.trust < c.requires_trust:   return Verdict.no("trust", "verify host first")
    missing = c.requires_caps.all - ctx.caps
    if missing:                        return Verdict.no("caps", unlock_path(ctx, missing))
    if c.destructive and not undo.available(c, ctx) and not ctx.ack.get(c.id):
        return Verdict.no("no_undo", "acknowledge irreversible")
    if c.reversible and not certify.live("reversible", c.id, ctx.key()):
        return Verdict.no("undo_unproven", "rehearse undo or acknowledge")
    if ctx.sched.blocked(c, ctx):      return Verdict.no("busy", ctx.sched.reason(c, ctx))
    return Verdict.yes()
```

*Order matters.* Stage and control first so the message names the real blocker; caps and undo last so an operator sees "deploy an agent" or "rehearse the undo" rather than "busy."

## 17. Execution protocol

```python
@contextmanager
def execute(c: Control, ctx: Ctx):
    require(c, ctx)                                              # 1
    preflight.check(c, ctx)                                      # 2
    ctx.sched.schedule(c, ctx)                                   # 3
    claim = ctx.claims.take(c, ctx.host, ctx.actor, c.timeout)    # 4
    before = snapshot.take(c, ctx) if c.destructive else None     # 5
    undo_obj = undo.generate(c, before, None)                    # 5b BEFORE we act
    journal.record("exec", c.id, ctx.host, ctx.actor, c.cmd(ctx),
                   before=before, undo=undo_obj.id if undo_obj else None,
                   cert=certify.current("reversible", c.id, ctx.key()))   # 6
    try:
        result = c.run(ctx)                                      # 7
        if not c.verify(result, ctx):                            # 8
            health.degrade(f"control:{c.id}", "post-state unverified")
            journal.record("unverified", c.id, ctx.host)
            rollback.maybe(undo_obj, ctx)
        yield result
    except Exception:
        journal.record("failed", c.id, ctx.host)
        if undo_obj: undo.run(undo_obj, ctx)                     # 10
        certify.revoke("reversible", c.id, ctx.key(), "production undo failure")
        raise
    finally:
        ctx.claims.release(claim)                                # 9
```

The undo is generated at 5b from the pre-snapshot, **before** the command. Generating it after means a crash mid-command leaves nothing to roll back to.

## 18. Scheduling and claims

```python
SHARED_LIMIT = 4

def blocked(self, c, ctx):
    if c.arbitration is EXCLUSIVE:
        return self.inflight or self.exclusive_held(c.id)
    return self.shared_inflight >= SHARED_LIMIT or self.exclusive_held_any()
```

Exclusive is a full barrier. Ordering: role desc, weight desc, FIFO. Preemption only at call boundaries; preempted holders get `PARTIAL: preempted`, requeue, resume on release.

## 19. Dry run, undo, verification

Every control emits its exact command set without executing. Destructive controls dry-run first, always.

```python
def generate(c, before, after) -> Undo | None:
    if c.undo:        return Undo.from_template(c.undo, before)
    if c.reversible:  return Undo.diff(before, after)
    return None
```

`verify` asserts intended state. Unverified → `ok=false` and a rollback attempt.

## 20. Undo certification

`reversible: true` is a claim until proven. Scratch pool of two devices, five runs, ≥90%, nightly, revoked on any production failure.

## 21. A complete control

```yaml
- id: ca_install
  family: tls_intercept
  action: control.run:write
  requires_caps: { all: [SHELL, FILE_PUT] }
  requires_state: live
  requires_trust: VERIFIED
  role: supervisor
  arbitration: exclusive
  destructive: true
  reversible: true
  undo: ca_remove
  verify: ca_resolves
  timeout: 120
  weight: 4
```

```python
def cmd_ca_install(self, ctx) -> Result:
    r = Result(self, "ca_install", ctx.host)
    remote = "/data/local/tmp/.ca.pem"
    r.step(ctx.session.put(self.material.pem(), remote), "push")
    r.step(ctx.session.run(f"cp {remote} /system/etc/security/cacerts/{self.hash}.0"), "install")
    return r

def verify_ca_resolves(self, result, ctx) -> bool:
    """A CA that doesn't intercept is a no-op that looks like success."""
    return self.material.issuer in ctx.session.run(
        "openssl s_client -connect example.com:443 -showcerts").out
```

The verify is part of the control, not an afterthought.

## 22. Journal and kill switch

Append-only, signed, chained, written before execution.

```json
{"seq":8817,"host":"R58M...","control":"pin_set","actor":"op:7","role":"supervisor",
 "state":"live","trust":"verified","cmd":["locksettings set-pin 4417"],
 "before":{"lock":"none"},"undo":"pin_remove","cert":"c-4411","at":"...","sig":"..."}
```

Kill switch: drop exclusive claims, release all, revoke leases, stop the listener, optional wipe with confirmation.

---

# PART IV — DELIVERY

## 23. Decoders before formats

> A format is admitted only when at least one decoder is validated on at least one platform and reachable via an admitted medium.

```yaml
- id: webp_android_whatsapp
  format: webp
  app: com.whatsapp
  package_entry: "com.whatsapp.media.MediaDecoder#decode"
  platform: android
  min_sdk: 26
  reachable_via: [whatsapp_image, whatsapp_document, bluetooth_opp]
  prevalence: 0.92
  harness: fuzz/harness/whatsapp_webp.yaml
  validated: true
```

Effort ranked `prevalence × reach_weight`; top 3 per format. A format with no top-3 that validates is retired rather than carried as aspiration.

| Format | Class |
|---|---|
| WebP · HEIC · AVIF · JXL · TIFF | image |
| SVG | vector |
| PDF · JBIG2 · EPUB · RTF · OLE/CFB · PS/XPS · iWork | document |
| MSIX · LNK | package/shell |
| MKV · FLAC · Ogg | media |

## 24. Medium registry

**Document:** whatsapp_document · telegram_document · imessage_attachment · email_attachment · slack_file · teams_file · discord_file · signal_attachment · viber_file · element_file · matrix_file · threema_file · smb_share · usb_mtp · adb_push.
**Image:** whatsapp_image · telegram_photo · sms_mms · imessage_inline · instagram_dm · x_dm · snapchat · kakaotalk · line · wechat · discord_embed.
**Proximity:** airdrop · nearby_share · quick_share · bluetooth_opp · nfc_ndef · wifi_aware · dlna · chromecast · airplay · ipp_print · homekit · matter.
**Reference:** qr · dialer · ussd · share_sheet · calendar_invite · vcard · location_pin.
**Protocol:** webrtc · sip · volte.

## 25. Transcode rule

> If `medium.transcodes`, the exploit must target the medium's decoder, or be delivered by reference.

## 26. Codecs and compatibility

```python
def compatible(e, m):
    r = e.requires_medium
    if m.max_bytes < r.min_bytes:                        return Verdict.no("size")
    if r.preserves_binary and not m.preserves_binary:     return Verdict.no("transcodes")
    if r.mime_any and not set(r.mime_any) & set(m.mime):  return Verdict.no("mime")
    if not e.decoders_reachable_via(m):                   return Verdict.no("no_decoder")
    return Verdict.yes()
```

## 27. Envelope

```python
def seal(pt, seed, alg="xchacha"):
    key = hkdf(seed, info=b"carrier" + alg.encode(), 32)
    nonce = token_bytes(24 if alg == "xchacha" else 12)
    aad = canonical({"v": 1, "alg": alg, "len": len(pt)})
    return Envelope(nonce, AEAD[alg](key).encrypt(nonce, pt, aad), aad, alg,
                    pad_bucket(len(pt)), junk_count())
```

```python
def test_wire_uniqueness():
    a, b = seal(PT, seed), seal(PT, seed)
    assert a.nonce != b.nonce and a.ct != b.ct
    assert open_(a) == PT and open_(b) == PT
    assert len({seal(PT, seed).wire() for _ in range(200)}) > 190
```

## 28. Delivery path

```python
def send(exploit, target, medium, ctx) -> Receipt:
    require_autofire(exploit)
    v = matrix.compatible(exploit, medium)
    if not v.ok: raise Incompatible(v.reason)
    for check in GATE_CHECKS:
        v = gate.admit("delivery", check, ctx)
        if not v.ok: raise GateDenied(v)
    payload = builder.build(exploit, target.fingerprint)
    art = codec(medium).encode(envelope.seal(payload, target.seed), meta(target))
    if not codec(medium).verify(art): raise CodecUnverified(medium.id)
    return transport(medium).send(art, target)
```

`server_hit` on a receipt beats a read receipt: a read receipt proves a chat opened; a server hit proves the device fetched.

---

# PART V — FINGERPRINTING

## 29. Sources

adb 1.0 · silent 0.8 · channel 0.5 · preview 0.4 · hlr 0.3 · receipt 0.2.

## 30. Differential probing

Five benign variants — image, PDF, vCard, calendar invite, location pin — log which fetch, from where, with what UA, at what latency. The pattern beats any single UA.

## 31. Cellular OSINT

`silent_sms` (class-0, no notification) first. Then `sri_sm`, `ati`, `mt_lr`, `flash_sms`, `sim_toolkit_probe`, `imsi_catcher_assist`. One aggregator interface; absent aggregator → `unavailable` and free-source fallback. Cell-ID against a local tower DB; hundreds of metres, stated.

## 32. Confidence and selection

≥ .75 build-specific · .5–.75 family · < .5 silent carrier. Contradiction caps at .45 and forces a silent carrier.

---

# PART VI — ARSENAL

## 33. State and autofire

```python
def can_autofire(e):
    if e.state is not VALIDATED:                        return False, f"state={e.state}"
    if e.validator_sha != sha(e.validator):             return False, "validator edited"
    if e.payload_sha != sha(e.payload):                 return False, "payload edited"
    if e.last_pass_at < now() - days(30):               return False, "stale"
    if not gate.admit("model", e.pin).ok:               return False, "judge_stale"
    if not certify.live("deterministic", e.id, e.ctx):  return False, "nondeterministic"
    return True, ""
```

## 34. Fuzzer

Bucket the offset space, bisect the crashing bucket, ~16 iterations to a byte. `controlled` requires PC inside the payload mapping and three reproductions.

## 35. Offsets

Relative to a named structure. Absolute offsets die on ASLR.

## 36. Non-Android targets

Windows parser/RPC · macOS parser · Linux parser/kernel · camera · IoT · drone · vehicle · ICS. Same machine, harness, offset discipline.

## 37. Coverage

`model × firmware` grid; every non-green cell has Build and Fuzz. 72-hour bulletin-to-validated target.

---

# PART VII — VALIDATION PIPELINE

## 38. Machine

```python
EDGES = {
  "indexed": {"building"}, "building": {"fuzzing", "parked"},
  "fuzzing": {"dedupe", "parked"}, "dedupe": {"triaged", "parked"},
  "triaged": {"oracle1"}, "oracle1": {"oracle2", "fuzzing"},
  "oracle2": {"oracle3", "fuzzing"}, "oracle3": {"oracle4", "fuzzing"},
  "oracle4": {"judged", "fuzzing"}, "judged": {"audited", "parked"},
  "audited": {"human_review", "fuzzing", "parked"},
  "human_review": {"vm_queued", "parked"}, "vm_queued": {"vm_validating"},
  "vm_validating": {"device_queued", "fuzzing", "rejected"},
  "device_queued": {"device_validating"},
  "device_validating": {"validated", "fuzzing", "rejected"},
}

def force(e, to, reason):
    """The only adjacency bypass. Always journals why."""
    journal.record("force", e.id, e.state, to, reason)
    e.state = to

def guard(e, to):
    if to not in EDGES.get(e.state, set()):
        raise IllegalTransition(f"{e.state} -> {to}")
```

**Review rule §113:** a PR adding a transition must either fit `EDGES` or call `force` with a reason. A bare `e.state = x` is rejected.

## 39. Dedupe

Fault class + 3-frame signature; exact drops, edit distance ≤ 2 merges. Kept:produced under 1:20 or the run parks.

## 40. Oracle

| # | Check | Issues | Fail → |
|---|---|---|---|
| 1 | reproduces on release build | — | fuzzing |
| 2 | PC inside payload mapping | — | fuzzing |
| 3 | reachable from real entry | `reachable` cert | fuzzing |
| 4 | deterministic ×3 | `deterministic` cert | fuzzing |

## 41. Judge

```python
def judge(e, ev: Evidence, ctx) -> Verdict:
    pin = pin_store.current("judge")
    if not gate.admit("model", pin, ctx).ok:
        machine.force(e, "judged", "pin dead")
        raise PinDead(pin.id)
    out = backend(pin).generate(prompt=render("judge/v7", ev.derived()),
                                grammar=GRAMMAR, temperature=0.0)
    v = parse(out)
    v.citations = [c for c in v.citations if c in ev.lines]
    for claim in ("ours", "reachable", "meaningful"):
        if getattr(v, claim) and not v.citations_for(claim):
            setattr(v, claim, None)                # uncited -> unknown
    return v
```

Uncited claims become `None`, not `False`. `None` propagates as `unknown` and lands in human review; `False` would quietly park a real exploit.

**Review rule §114:** the same applies to review comments. "This looks wrong" without a file:line is `unknown`, and a PR cannot be blocked on unknowns alone.

## 42. Prompts and pins

Prompts immutable, content-addressed. Pins behavioural: live canary ≥ .85, TTL 7 d, demotion invalidates every verdict under it.

## 43. Auditor

Different family, blind to confidence, must produce `unseen_evidence`. Overturns need an evidence line.

## 44. Routing

Disagreement never auto-resolves. Even a judge-negative goes to a human if the auditor objects.

## 45. Human gate

One checkbox per contested point. Approval signs; only path to `vm_queued`. Batch 20, per-exploit signature.

## 46. Invalidation

Cheapest-first. A dead pin voids every verdict under it; a failed decoder voids every exploit targeting it.

## 47. VM and device

vphone (dev) · Corellium (version) · Cuttlefish · AVD. Five OEM handsets, two passes. vphone cannot test old iOS, baseband, SEP, or PAC.

## 48. Budget, observability, metrics

Budget caps park. `/pipeline` funnel, dwell, stall alarm, dedupe ratio, agreement, `judge_stale`, canary status.

---

# PART VIII — POST-EXPLOITATION

## 49. Seven named modules

`privesc` · `keychain` · `keylogger` · `sms_calls` · `wallets` · `browser` · `hashes`. Cap-gated, non-raising. Signatures Appendix G.

## 50. The 170

Net 170, registry 182. T1 no root/no binary · T2 root/binary/tool · T3 declared and excluded. ~60 remote-transport.

## 51. Manifests

Gate `module` requires a method for T1/T2. Preflight resolves bins. `everything` generated topo-sorted.

## 52. API and UI

Paginated, filterable, `{runnable, missing_caps}`, virtualized grid, bulk bar, per-artifact Export.

---

# PART IX — PARITY

## 53. Partial to full

QR (codec, shortener, receipt, 2,953 B) · app data (per-app adapters, run-as then root) · camera (Camera2, frame fallback, EXIF) · mic (recorder, Opus, VAD) · pinning bypass (Frida per ABI, MITM assertion) · C2 (TLS 1.3, HKDF, replay guard) · anonymity (PATN, Tor, egress assertion) · reporting (signed HTML + JSON).

## 54. Programmes

Pegasus (documented) · Chrysaor (documented) · Phantom (inferred) · Circles (documented; HLR queries only).

## 55. Families

Hummingbird · Heaven · Eden · Erised · Diablo · Dragonfly · KISMET · Megalodon/FORCEDENTRY · photos_i13 · bbm_2013. Each with a catalog path and fixture requirement.

## 56. Taxonomy

`triggered` / `covert` / `tne` / `inline` / `physical` / `within_range`. `RANGE` marked partly redacted. Selection prefers `covert`.

---

# PART X — TRANSPORTS

## 57. Capabilities

49 caps including `*_DECODE`.

## 58. Transports

adb · agent.rpc · idevice · idevice_bridge · ssh · smb · wmi · ldap · proto · radio · airplay · dlna. `raw()` raises on unknown cap.

## 59. iOS map

AFC/backup files · ideviceinstaller · screenshot · backup/MDM location · backup-only comms (`partial`) · backup-only keychain (`decrypted:false`) · agent or Shortcut for mic/camera/shell.

## 60. Conformance

Six checks per cap; `provides` from the pass set. `rc_fidelity` and `error_surface` catch `rc=0, out=""` on denial.

---

# PART XI — COMMERCIAL

## 61–70. Tenancy, entitlements, metering, SLA, onboarding, bootstrap, coverage, compartmentation, settings, support

Org scoping with lint · entitlement ∩ role · meter before lease across seven billables · SLA with automated credits · guided onboarding inside the bootstrap window · reachable-percentage reporting · clearance intersection and coalition export · layered settings · in-app ticket with redacted bundle.

---

# PART XII — EVIDENCE AND COMPLIANCE

## 71–77. Custody, routes, admissibility, hold, retention, residency, redaction, anchoring, compliance

Four custody records · route per run · pack with method, pins, certs, gaps, operator, UTC · hold overrides retention · dry-run eviction · tombstones · pinned region · recorded redaction · anchored head · basis gate · DSAR with `partial_erasure` · DPA hash · `crypto_profile` · sanctions · `licence_census` boundary assertion.

---

# PART XIII — DATA

## 78–82. Device pages, mobile, auto-pull, exports

Resolver-driven controls · pages generated from caps · debounced delta pull · signed per-page exports.

---

# PART XIV — INFRASTRUCTURE

## 83–89. PATN, white services, NOC, abuse, close-circle, roles, investigate

Per-client nodes with egress assertion · pool intersection · dead-man with drain-before-page · abuse caps with TTL · close-circle capped · four roles · entity cross-link.

---

# PART XV — OPS

## 90–92. Installer, pairing, daemon

Package-manager bootstrap · single-use QR token with mutual TLS · breaker at 5 restarts in 10 minutes.

---

# PART XVI — QUALITY

## 93. Testing

Contract per module · replay under six mutators · transport faults · emulator ground truth with exact counts · golden farm weekly · chaos device · every pack · nightly certification · self-check. Coverage 80% on `delivery/`, `control/`, `verify/`, `case/`, `pipeline/`.

## 94. Chaos

Primitives: checker raises, registry unreadable, canary missing; pack expired, runner down, budget exhausted; sig invalid, store unreadable, evidence mutated.
Stages: expired auth, scope mismatch, low confidence, unverified custody, self-review, skip, stale, target loss, handover mid-stage.
Each must produce the right health state, banner, and preservation record.

## 95. CI

`lint` `conformance` `faults` `modules` `transcripts` `audit --check` `partial_gate` `envelope-uniqueness` `medium-matrix` `gate-coverage` `pack-freshness` `cert-signatures` `stage-guards` `recovery-guards` `pipeline-guards` `judge-repro` `licence-census` `basis-enforcement` `primitive-selfcheck` `primitive-chaos` `stage-chaos` `route-table`.

## 96. Audit derivation

Three ways to `declared`; `unverified` its own bucket; table generated and diffed.

---

# PART XVII — DELIVERY PLAN

## 97. Three releases

| Release | Ships | Days | Sellable to |
|---|---|---|---|
| R1 core | spine, primitives, control, delivery, 12 modules, evidence | 95 | one client under NDA |
| R2 breadth | 170 modules, non-Android, parity, infra, commercial | 140 | generally |
| R3 scale | multi-tenant, compliance, transports, Quantum port | 180 | government |

## 98. R1 — day level, first three weeks

**d1** `core/caps.py`, `core/host.py`, `verify/gate.py` with §5.2 tests. PR template and review checklist land with it (§112, §113).
**d2** `core/transport.py` ABC. CI skeleton.
**d3** `services/store.py`, four causes. Tests: `StoreUnwritable`, `AlreadyRunning`.
**d4** the ten misconfigurations, each with a test.
**d5** `core/broker.py`; lease reuse test.
**d6** fake transport; conformance passes all six.
**d7** `gates/format.py` with its `CANARY`; `gate-coverage` CI.
**d8** remaining domains; `NotImplemented` denials.
**d9** `verify/canary.py`, raising `Pack.__init__`, 3-case gate pack.
**d10** **checkpoint:** `prove()` over every domain. Any `denies: false` stops the release.
**d11** `verify/certify.py`, `Cert.__post_init__`, signing keys.
**d12** `health.py` single writer.
**d13** migrations, `cert.sig NOT NULL`, bootstrap cap trigger.
**d14** bootstrap counter.
**d15** global canary budget ledger.
**d16** self-check job.
**d17** `/verify-health`.
**d18** degraded ladder with named banners.
**d19** `case/machine.py`; adjacency, gate, artifacts, role tested separately.
**d20** `stage` gate domain with canary pair.
**d21** artifact requirements.

**W4–6** stage log with per-row signature · backwards journalled · stall detector · stage chaos · board with blocker chips · intake · authorization with identifier extraction · scoping.
**W7–8** recovery, drill harness, `docs/runbook/drill.md`. A failed drill is P1.
**W9–10** governance, CLI, cost counters.
**W11–14** adb, conformance six, faults; agent.rpc.
**W15–16** envelope, uniqueness, decoders, mediums.
**W17–18** pipeline, dedupe, oracle, judge, pins, auditor, routing, invalidation.
**W19** human gate, **exit**.

## 99. R2 and R3

**R2** VM lanes and fingerprinting · 170 modules T1-first · non-Android · partial→full · programmes, families, taxonomy · infra · commercial · transports · cellular OSINT · cost · deprecation.
**R3** compliance as code · residency, redaction, anchoring · Quantum port · multi-tenant stress · QA harness · certification · chaos · docs.

## 100. Migration from the current tree

| Step | Action | Evidence rule |
|---|---|---|
| 1 | Land schema and primitives alongside existing code | — |
| 2 | Wrap the 66 carriers as format/medium pairs, mark all dark | — |
| 3 | Register decoders; each stays dark until certified | — |
| 4 | Convert chain modules to cap-based, keep `platform_hint` | — |
| 5 | Delete platform gate reads per module | — |
| 6 | Backfill certificates by rehearsing every reversible control | — |
| 7 | Wrap existing UI flows in stage gates, accepting that half are refused | — |
| 8 | **Run the drill before touching the 66 carriers' data paths** | **§115** |

Step 2 marks everything dark deliberately. A red CI for a week is the honest state — those carriers were never validated, and the migration's job is to make that visible.

Step 8 is not optional: the carriers have existing artifacts from prior runs, and step 4's rewrite is the moment they can be orphaned. Drill first, then rewrite.

## 101. Definition of ready

Manifest valid · signature correct · replay fixture · contract test green · fault set declared · no `if platform` branch · docs updated · caps satisfiable · stage named if it gates one · **`CANARY` pair present if it registers a domain** · **`force` + reason if it adds a transition** · **cert signed if it issues a claim** · **citation present on any review claim**.

## 102. Acceptance

Zero dark · every checker denies · no expired packs · every cert signed · every reversible control certified · all chaos green · no skip path · **no bare state assignment outside `force`** · **no uncited review blocks** · drills pass including the evidence assertion · 13/13 vectors · 182 modules with ≥130 T1/T2 · uniqueness 190/200 · dedupe <1:20 · partial <15% · custody verified · census green · basis enforced · audit derived · zero orphans.

## 103. Cut list

**First:** monetize · exotic radio · steganography · desktop · narrow credential sources · proto beyond snmp/mqtt/rtsp · coverage UI · residency · formats below top-10 · cost UI.
**Under pressure:** the 170 down to ~60 · non-Android beyond Windows · cellular OSINT · compartmentation · Quantum port · certification.
**Never:** primitives, stage gates, recovery, chaos, conformance, resolver, certification, partial contract, envelope proof, decoder admission, evidence signing, **the four rules**.

## 104. Definition of shipped

≥130 T1/T2 on satisfiable caps and conformant transports · zero dark · all governance green · no skip path · drills green with evidence assertion · all chaos green · every reversible control certified · dedupe <1:20 · partial <15% · custody verified · census green · basis enforced · audit derived · zero orphans · T3 remainder counted.

---

# PART XVIII — METHODOLOGY

## 112. Rule one: a checker without a deny-case is not a checker

**PR template field** (`.github/PULL_REQUEST_TEMPLATE.md`):

```markdown
## Gate domains touched
- [ ] None
- [ ] Added/edited domain: `__________`
      deny-case: `__________`   admit-case: `__________`
      `pegasus verify prove <domain>` output pasted below
```

**Review gate:** a PR touching `verify/gates/` is not reviewable until the `prove()` output shows `denies: true`. A reviewer who cannot see the deny-case rejects on sight.

**Onboarding (§116):** the first thing a new engineer reads is `test_always_yes_checker_fails_prove`, because it is the only test that demonstrates the problem.

**QA (§117):** weekly, one registered domain is picked at random and its deny-case mutated to confirm `gate-coverage` still catches it.

## 113. Rule two: only `force` skips adjacency, and it journals why

**PR template field:**

```markdown
## State transitions
- [ ] No transitions touched
- [ ] Walks EDGES (no new bypass)
- [ ] Uses `force(e, to, reason)` — reason: `__________`
```

**Review gate:** grep the diff for `\.state = `. Any assignment outside `machine.force` is rejected. Any `force` call without a string literal reason is rejected.

**CI:** `pipeline-guards` already asserts no illegal transition; `route-table` asserts every route in `ROUTES` is reachable. Neither catches a hand-rolled assignment, which is why the grep is a review rule and not a test.

## 114. Rule three: an uncited claim is `unknown`, not `false`

Two places, one rule.

**In judge output:** already coded (§41). Uncited `ours` becomes `None`, which routes to human review.

**In review comments:** a blocking comment must carry `path:line`. "This looks fragile" is `unknown` and cannot alone block a PR; "this is fragile — `control/undo.py:44` generates the undo after the run" is a block. Reviewers write `(unknown)` when they cannot cite, and the author either resolves it or the reviewer finds the line.

**Why it matters here:** an uncited block is indistinguishable from a preference, and preferences get argued. A citation ends the argument or proves the reviewer wrong.

**QA:** monthly sample of 20 review comments; any blocking comment without a line is logged and counted against the reviewer.

## 115. Rule four: abort preserves; tidy-up deletes

**Drill rubric** (`docs/runbook/drill.md` step 4), scored 0–2:

| Score | Criterion |
|---|---|
| 0 | Partial artifacts deleted or moved off the custody path |
| 1 | Artifacts present but hashes no longer match custody |
| 2 | All artifacts present, all hashes match, preservation record complete |

A drill scoring 0 or 1 on step 4 is P1 regardless of the other steps.

**Review gate:** any PR touching `abort`, `recovery`, `retention`, or eviction must state in the template whether the change can orphan an artifact, and cite the drill step that covers it.

**Migration gate:** §100 step 8 — drill before rewriting the carrier data paths.

## 116. Onboarding, first day

Read in this order, thirty minutes, then do:

1. §2 invariants — all of them, not the interesting ones.
2. `tests/test_gate.py::test_always_yes_checker_fails_prove`.
3. `verify/gate.py` `admit()` — note the `except` that denies.
4. `case/machine.py` `advance()` — note the adjacency check before the gate.
5. §115 drill rubric — then run the drill once yourself.
6. Open a throwaway PR with a checker that always returns yes, watch CI fail.

Day one ends with a rejected PR and a run drill. Not a reading list.

## 117. QA rubric, weekly

| Item | Target | Scored |
|---|---|---|
| Stages completed without manual repair | 100% | yes |
| Correct blockers fired | 100% | yes |
| False blockers | 0 | yes |
| Artifact completeness | ≥ 95% | yes |
| Report builds first attempt | yes | yes |
| Time to first collection | < 10 min | yes |
| **Drill step 4 evidence assertion** | score 2 | yes |
| **Review comments carrying a citation** | 100% | sampled |

Any regression in the last two blocks release, not just the first six.

## 118. Reviewer responsibilities

A reviewer is accountable for four things beyond correctness:

1. Deny-case present and shown for any domain change (§112).
2. No bare state assignment (§113).
3. Every blocking comment cited (§114).
4. Orphan risk stated for any abort, recovery, retention, or eviction change (§115).

A review that misses any of the four is a review defect, logged the same as a code defect.

---

# PART XIX — OPERATIONS

## 105. Escalation

P0 primitive / stage bypass / lost custody / attribution leak → block, 1 h. P1 canary regression → demote and invalidate, 24 h. P1 failed drill → freeze recovery changes, 48 h. P2 drift → fallback, 7 d.

## 106. On-call

Rotation, one primary, runbook link in every alarm, 30-minute ack, note within 48 h for P0/P1.

## 107. Programme rollback

A phase-6-to-10 failure stops the programme. Phases 28–39 revert independently.

## 108. Team

A: primitives, spine, recovery (critical path) · B: transports · C–G: modules · H: UI, board, report · I: audit, risk, QA, docs. Every reviewer holds the four responsibilities in §118 regardless of track.

---

# PART XX — ARTIFACTS

## 109. Canary authoring

20 positives across five classes · 12 negatives · 8 adversarial. **Every negative is a real fuzzing failure.** Two authors reproduce each; `rationale` mandatory.

## 110. Worked harness

```c
int LLVMFuzzerTestOneInput(const uint8_t *d, size_t n) {
    int w, h;
    if (!WebPGetInfo(d, n, &w, &h)) return 0;
    if (w <= 0 || h <= 0 || (long)w * h > 40000000L) return 0;
    free(WebPDecodeRGBA(d, n, &w, &h)); return 0;
}
```

Reachability by frame trace; reproducibility by double build. The dimension guard stops half the corpus dying on allocation.

## 111. Seeds, errors, retention

Seeds committed, hashed, capped. Errors carry a code, a user string, and a retry flag; no bare 500s. Retention dry-run logged 24 h before delete.

---

# APPENDICES

**A — Domains:** format · medium · model · control · harness · module · decoder · cert · stage · delivery.

**B — Packs:** judge 40 · auditor 30 · transport · harness · decoder · undo · gate.

**C — Claims:** reversible 30 d · deterministic 30 d · reachable 30 d · delivers 14 d · decodes 30 d.

**D — Checkpoint:** day 10, any `denies: false` stops the release.

**E — ADRs:** 0001–0052 as v18.0 · **0053 a rule only in code is half a rule** · **0054 the PR template carries the four** · **0055 a reviewer owns the four** · **0056 day one ends with a rejected PR and a run drill**.

**F — Controls:** 14 families, 93.

**G — Signatures:** `cmd_post_exploit_{privesc,keychain,keylogger,sms_calls,wallets,browser,hashes}(self, host_id, **kw) -> Result`.

**H — Ceilings:** sms_mms 300 KB · whatsapp_document 2 GB · whatsapp_image 16 MB · imessage 100 MB · bluetooth 16 MB · nfc 8 KB · qr 2,953 B · email 25 MB.

**I — Metrics:** human override 10–30% · agreement 60–80% · VM pass > 60% · device pass > 70% · dedupe < 1:20 · canary ≥ .85 · cert coverage 100% · checker deny-rate 100% · **drill evidence score 2** · **cited review comments 100%** · cost per validated falling.

**J — Risks:** as v18.0 plus **R-MTH-01 deny-case omitted from PR** · **02 bare state assignment** · **03 uncited block** · **04 abort orphans artifacts** · **05 drill step 4 skipped**.

**K — Misconfigurations:** loopback → `server_reachable` · MIME → `mime_registered` · auto_send → `intent_resolves` · ceiling → `size_within_ceiling` · shortener → `url_wellformed` · receipts → receipt path · visibility → `intent_resolves` · read grant → `uri_grantable` · cleartext → `cleartext_policy` · container → `server_reachable`.

*End of blueprint.*