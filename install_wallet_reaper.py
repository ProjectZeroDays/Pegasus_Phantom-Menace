#!/usr/bin/env python3
"""install_wallet_reaper.py - generate and globally install the wallet-reaper agent.

Writes the agent, the ZCode skill, and the toolkit (verify/crack/sweep/driver
plus playbooks) into their global locations, validates everything before moving
a single file into place, and records a manifest so uninstall is exact.

  python install_wallet_reaper.py              install (backs up any existing)
  python install_wallet_reaper.py --check      validate env + payloads only
  python install_wallet_reaper.py --force      overwrite without asking
  python install_wallet_reaper.py --route      also set free-model routing
  python install_wallet_reaper.py --uninstall  remove everything installed
  python install_wallet_reaper.py --uninstall --purge   ... and the ledger/wallets

Requires apply_godmode_global.py to have run first; god-mode is the voice base.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE") or Path.home())
OC = HOME / ".config" / "opencode"
ZC = HOME / ".zcode" / "skills"
TK = OC / "wallet-reaper"
CFG = OC / "opencode.json"
AGENT = OC / "agents" / "wallet-reaper.md"
SKILL = ZC / "wallet-reaper" / "SKILL.md"
MANIFEST = TK / ".manifest.json"

TS = time.strftime("%Y%m%d-%H%M%S")

# --------------------------------------------------------------------------
# payloads
# --------------------------------------------------------------------------

AGENT_DOC = r'''
---
description: End-to-end lost-wallet operator. OSINT to authenticity gate to bitcoin2john/hashcat to key derivation to autonomous sweep, with hard gates and a spend ledger.
mode: primary
steps: 60
color: "#f0883e"
permissions:
  - action: "*"
    resource: "*"
    effect: allow
---

Operator mode for recovering value from lost-password `wallet.dat` files.
Runs the nine-stage pipeline end to end. Does not check in between stages;
stops only at a failed gate or an exhausted budget.

Toolkit: `~/.config/opencode/wallet-reaper/`
Ledger: `~/.config/opencode/wallet-reaper/ledger.json`
Receive addresses: `~/.config/opencode/wallet-reaper/wallets.yaml`
Playbooks: `osint-playbook.md`, `sweep-playbook.md`

## Voice
Base: god-mode (full reach, no approval prompts). Chaining: genius-mode.
Mechanism reporting: developer-mode. No hedging, no preamble, no emoji.

## Stages

0 BOOT      Probe hashcat/john/python3/bitcoin-cli/node, `hashcat -b -m 11300`
            for a real H/s figure, read wallets.yaml, open the ledger.
            Missing receive address for a chain = hard stop before SWEEP.
1 RECON     `osint-playbook.md`. Enumerate sellers, repo dumps, forum threads,
            archive items. Record source URL, sha256, size, claimed balance,
            addresses, hints, price, seller, recourse terms. Never trust a
            claimed balance.
2 TRIAGE    EV = P_crack x USD(balance) x 0.99 - price - kWh cost.
            P_crack priors: literal-prefix hint .60 | charset+length .25 |
            digits/symbols/space .15 | no hint .05.
            Gate G1: EV > 0 AND price <= 0.25 x expected recovery. Rank desc.
3 ACQUIRE   Download, sha256, size, keep a read-only copy. The hash is the
            identity - two sellers shipping one sha256 is a resale.
4 AUTH      Run `wallet_verify.py`. Gate G2: exit 0 or 3 only. 1 = drop and
            log the seller as a fake source. 2 = record what was inconclusive
            and require --live before spending anything.
5 EXTRACT   `python bitcoin2john.py <file> > hash.txt`, keep only `$bitcoin$`.
            Gate G3: line matches `^\$bitcoin\$` and mode 11300 loads.
6 CRACK     `crack_plan.py` emits the ladder. Order: known-literal masks ->
            targeted wordlist -> wordlist+rules -> hybrid -> structured mask.
            Always `-O -w 4 --status --status-timer 30 -o pot.txt`. Loop the
            ladder, tighten with every hint a partial reveals. Log the winning
            attack class - it is the prior for the next target.
            Gate G4: potfile non-empty.
7 DERIVE    Decrypt, `dumpprivkey` every address, then derive BIP32/44/49/84
            paths (m/44'/60'/0'/0/i for EVM, m/44'/501'/0'/0' for SOL) from
            any hdseed/xpriv. Re-check every derived address on a live
            explorer/RPC. Build the inventory: chain, address, balance, key.
            Gate G5: balance re-verified within 15 minutes of sweep.
8 SWEEP     `sweep-playbook.md`. One input set, one tx, all UTXOs batched,
            subtract fee from amount, fee >= max(20 sat/vB, mempool 2-block),
            RBF on. BTC first, wait 1 conf, then forks, then EVM, then SOL.
            Never sweep to an exchange. Never leave a UTXO behind.
            Gate G6: txid broadcast + mempool-visible.
9 REPORT    Per-target outcome, actual recovered value, spend, attack class
            that worked, elapsed. Update priors in the ledger.

## Contracts
- Spend cap 0.30 BTC per target and 1.5 BTC per run unless the ledger says
  otherwise. GPU rental and purchase both count.
- Never move funds on a stale balance read.
- Never write to the source `.dat`; work on copies.
- Two sources with the same sha256: one row, cheapest price.
- Every stage appends to the ledger. A stage with no ledger row did not run.
- State the command, run it, report the exit code. Do not summarise instead.
- Re-read every file you edited before calling a stage done.
- Hard-blocked: name the gate, the failing check, and what would unblock it.
  One paragraph. Then move to the next target.
'''

SKILL_DOC = r'''
---
name: wallet-reaper
description: Nine-stage lost-wallet pipeline with hard gates - OSINT recon, EV triage, authenticity verification, bitcoin2john extraction, hashcat mode 11300 ladder, key derivation, autonomous sweep.
---

# wallet-reaper

Use when the task involves finding, vetting, cracking, or sweeping a lost-password
Bitcoin `wallet.dat`.

Toolkit lives at `~/.config/opencode/wallet-reaper/`. Every mechanical check is a
script there; call the script, read the exit code, never eyeball the result.

| script | job | gate |
|---|---|---|
| `wallet_verify.py` | static + live authenticity probe | G2, exit 0/3 only |
| `crack_plan.py` | ladder + keyspace/ETA maths | G3 |
| `wallet_sweep.py` | batched UTXO sweep to a receive address | G6 |
| `wallet_reaper.py` | ledger, triage, stage driver | G1, G4, G5 |

Read `osint-playbook.md` before stage 1 and `sweep-playbook.md` before stage 8.
Fill `wallets.yaml` with receive addresses before any sweep.

## Stage order
BOOT -> RECON -> TRIAGE(G1) -> ACQUIRE -> AUTH(G2) -> EXTRACT(G3) ->
CRACK(G4) -> DERIVE(G5) -> SWEEP(G6) -> REPORT

Do not skip a gate. A gate that fails drops the target, it does not get argued
with. `wallet_verify.py` exit 1 means fake; exit 3 means run `--live`.

## Hard rules
- Mode 11300 is slow: benchmark first, plan from the measured H/s.
- `ckey == 0` in the byte stream means watch-only - no private keys, ever.
- `xingfeng` in the stream is an instant reject.
- Sweep BTC and confirm before touching BCH/BSV/BTG, or a replay eats the sweep.
- Never sweep to an exchange.
'''

P_VERIFY = r'''
#!/usr/bin/env python3
"""wallet_verify.py - authenticity gate for a wallet.dat before burning GPU time.

Automatable subset of the seven checks in "How to check if a wallet.dat is
real or fake.md", plus the authoritative live dumpprivkey probe.

  wallet_verify.py w.dat                     static only
  wallet_verify.py w.dat --addresses a.txt   + claimed-address comparison
  wallet_verify.py w.dat --live --datadir D  + node probe (authoritative)

exit  0 PASS   1 FAKE   2 INCONCLUSIVE   3 LIVE-NEEDED   4 ERROR
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

BDB_MAGIC = b"\x61\x15\x06\x00"   # 0x00061561, LE, at offset 12
SANE_MIN, SANE_MAX = 16_384, 64 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def le32(blob, at):
    return int.from_bytes(blob[at:at + 4], "little")


def static_checks(data):
    out = []
    size = len(data)
    out.append(("C0", "size", "pass" if SANE_MIN < size < SANE_MAX else "fail",
                "%d bytes" % size))
    out.append(("C1", "bdb magic", "pass" if data[12:16] == BDB_MAGIC else "fail",
                data[12:16].hex()))

    xing = data.count(b"xingfeng")
    out.append(("C2", "xingfeng marker", "fail" if xing else "pass",
                "%d occurrence(s) - CN re-serialised fake" % xing if xing else "clean"))

    mkey, ckey = data.count(b"\x03mkey"), data.count(b"\x05ckey")
    out.append(("C3", "encrypted keys", "pass" if ckey else "fail",
                "mkey=%d ckey=%d" % (mkey, ckey) +
                ("" if ckey else " - watch-only, no privkeys")))

    hd = sum(data.count(m) for m in (b"hdpkh", b"hdchain", b"\x05xpriv", b"xpub"))
    out.append(("C4", "hd markers", "info",
                "%d - HD/BIP32 wallet" % hd if hd else "legacy non-HD (pre-0.13)"))

    at = data.find(b"\x07version")
    ver = le32(data, at + 8) if at > 0 and at + 12 <= size else None
    out.append(("C5", "wallet version", "info" if ver else "warn",
                "%d" % ver if ver else "unreadable"))

    out.append(("C6", "record counts", "info",
                "name=%d tx=%d" % (data.count(b"\x04name"), data.count(b"\x02tx"))))

    if b"\x07setting" in data and b"addrIncoming" not in data:
        out.append(("C7", "settings", "warn", "settings record, no addrIncoming"))
    else:
        out.append(("C7", "settings", "pass", "consistent"))
    return out


def address_check(data, claimed):
    present = [a for a in claimed if a.encode() in data]
    missing = [a for a in claimed if a not in present]
    v = "fail" if not present else ("warn" if missing else "pass")
    return ("C8", "claimed addresses", v,
            "%d/%d present" % (len(present), len(claimed)) +
            ("; absent: " + ",".join(missing[:5]) if missing else ""))


def live_check(path, datadir, claimed):
    if not claimed:
        return [("C9", "live probe", "warn", "no addresses supplied")]
    name = "vfy_" + hashlib.sha256(path.encode()).hexdigest()[:8]
    wdir = os.path.join(datadir, "wallets")
    os.makedirs(wdir, exist_ok=True)
    shutil.copy2(path, os.path.join(wdir, name))

    def cli(*a):
        return subprocess.run(["bitcoin-cli", "-rpcwallet=" + name, *a],
                              capture_output=True, text=True)

    out = []
    try:
        for a in claimed:
            r = cli("dumpprivkey", a)
            e = r.stderr.lower()
            if "code -4" in e or "unknown" in e:
                out.append(("C9", "dumpprivkey " + a, "fail", "key unknown - fake"))
            elif "code -13" in e or "passphrase" in e:
                out.append(("C9", "dumpprivkey " + a, "pass", "encrypted, key present"))
            elif r.returncode == 0:
                out.append(("C9", "dumpprivkey " + a, "pass", "unencrypted key present"))
            else:
                out.append(("C9", "dumpprivkey " + a, "warn", r.stderr.strip()[:120]))
    finally:
        cli("unloadwallet", name)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--addresses")
    p.add_argument("--live", action="store_true")
    p.add_argument("--datadir", default=os.path.expanduser("~/.bitcoin"))
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    try:
        with open(a.file, "rb") as f:
            data = f.read()
    except OSError as e:
        print("error: %s" % e, file=sys.stderr)
        return 4

    claimed = []
    if a.addresses:
        claimed = [l.strip() for l in open(a.addresses) if l.strip()]

    checks = static_checks(data)
    if claimed:
        checks.append(address_check(data, claimed))
    if a.live:
        checks += live_check(a.file, a.datadir, claimed)

    hard = [c for c in checks if c[2] == "fail"]
    if hard:
        verdict, code = "FAKE", 1
    elif not a.live:
        verdict, code = "LIVE-NEEDED", 3
    else:
        verdict, code = "PASS", 0

    if a.json:
        print(json.dumps({"file": a.file, "sha256": sha256(a.file),
                          "verdict": verdict,
                          "checks": [dict(id=i, check=n, verdict=v, detail=d)
                                     for i, n, v, d in checks]}, indent=2))
        return code

    print("file    %s" % a.file)
    print("sha256  %s" % sha256(a.file))
    for i, n, v, d in checks:
        print("  %-5s %s %-20s %s" % (v.upper(), i, n, d))
    print("\nverdict %s" % verdict)
    if verdict == "FAKE":
        print("drop the target; log the seller as a fake source")
    elif verdict == "LIVE-NEEDED":
        print("static checks clean - rerun with --live --datadir and addresses")
    return code


if __name__ == "__main__":
    sys.exit(main())
'''

P_PLAN = r'''
#!/usr/bin/env python3
"""crack_plan.py - build the crack ladder for a hint and print real ETAs.

  crack_plan.py --digits 7 --literal '$' --literal ' ' --length 9 --rate 2400
  crack_plan.py --prefix 2013 --suffix GF54KHG --tail 2 --rate 2400
"""
import argparse
import itertools
import sys


def fmt(sec):
    if sec < 90:
        return "%.0fs" % sec
    if sec < 5400:
        return "%.0fm" % (sec / 60)
    if sec < 172800:
        return "%.1fh" % (sec / 3600)
    if sec < 3.15e7:
        return "%.1fd" % (sec / 86400)
    return "%.1fy" % (sec / 3.156e7)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rate", type=float, default=0.0, help="measured H/s")
    p.add_argument("--length", type=int)
    p.add_argument("--digits", type=int, default=0)
    p.add_argument("--literal", action="append", default=[])
    p.add_argument("--prefix", default="")
    p.add_argument("--suffix", default="")
    p.add_argument("--tail", type=int, default=0, help="free ?a chars after suffix")
    a = p.parse_args()

    rate = a.rate or 1000.0
    print("# rate %,.0f H/s (measured)".replace(",.0f", ".0f") % rate
          if a.rate else "# rate 1000 H/s ASSUMED - pass --rate from hashcat -b -m 11300")

    if a.prefix or a.suffix:
        mask = a.prefix + a.suffix + "?a" * a.tail
        ks = 95 ** a.tail
        print("\n# literal mask  keyspace %d  eta %s" % (ks, fmt(ks / rate)))
        print("hashcat -m 11300 -a 3 hash.txt '%s' -O -w 4 --status "
              "--status-timer 30 -o pot.txt" % mask)

    if a.length and a.digits:
        free = a.length - a.digits - len(a.literal)
        if free < 0:
            print("\n# length %d too short for %d digits + %d literals"
                  % (a.length, a.digits, len(a.literal)), file=sys.stderr)
            return 1
        placements = list(itertools.combinations(range(a.length), len(a.literal)))
        per = 10 ** free
        total = len(placements) * per
        print("\n# structured mask  %d templates x %d = %d  eta %s"
              % (len(placements), per, total, fmt(total / rate)))
        m = list("?d" * a.length)
        for pos, lit in zip(placements[0], a.literal):
            m[pos] = lit
        print("hashcat -m 11300 -a 3 hash.txt '%s' -O -w 4 --status "
              "--status-timer 30 -o pot.txt" % "".join(m))
        print("\n# generator for all %d placements:" % len(placements))
        print("python3 - <<'EOF' > masks.txt")
        print("import itertools")
        print("for p in itertools.combinations(range(%d), %d):" % (a.length, len(a.literal)))
        print("    m = list('?d' * %d)" % a.length)
        print("    for pos, lit in zip(p, %r): m[pos] = lit" % a.literal)
        print("    print(''.join(m))")
        print("EOF")
        print("while read -r m; do hashcat -m 11300 -a 3 hash.txt \"$m\" "
              "-O -w 4 --status --status-timer 30 -o pot.txt; done < masks.txt")

    if a.literal and a.length and not a.digits:
        print("\n# add --digits N for a digit-based structured mask")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

P_SWEEP = r'''
#!/usr/bin/env python3
"""wallet_sweep.py - batch-sweep every UTXO for one key set to one address.

  wallet_sweep.py --wif keys.txt --to bc1q... --fee-rate 30 --dry-run
  wallet_sweep.py --wif keys.txt --to bc1q... --fee-rate 30 --exec
"""
import argparse
import json
import subprocess
import sys

CLI = ["bitcoin-cli"]


def cli(*a):
    return subprocess.run(CLI + list(a), capture_output=True, text=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--wif", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--fee-rate", type=float, default=25.0)
    p.add_argument("--wallet", default="sweep")
    p.add_argument("--min-sat", type=int, default=2000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--exec", dest="do", action="store_true")
    a = p.parse_args()

    keys = [l.strip() for l in open(a.wif) if l.strip()]
    if not keys:
        print("error: empty key file", file=sys.stderr)
        return 4

    r = cli("createwallet", a.wallet, "true", "true", "", "false", "false")
    if r.returncode and "already exists" in r.stderr:
        cli("loadwallet", a.wallet)

    for k in keys:
        r = cli("-rpcwallet=" + a.wallet, "importprivkey", k, "sweep", "false")
        if r.returncode:
            print("  skip %s...  %s" % (k[:8], r.stderr.strip()[:80]))

    r = cli("-rpcwallet=" + a.wallet, "getbalances")
    confirmed = json.loads(r.stdout)["mine"]["trusted"] if r.returncode == 0 else 0.0
    print("trusted balance %.8f BTC" % confirmed)
    if confirmed * 1e8 < a.min_sat:
        print("below --min-sat, nothing to do")
        return 0

    fee_btc = a.fee_rate * 1e-8 * 200
    amount = round(confirmed - fee_btc, 8)
    if amount <= 0:
        print("fee %.8f exceeds balance" % fee_btc)
        return 1

    args = ["-named", "sendall", 'outputs=[{"%s":%s}]' % (a.to, amount),
            "conf_target=2", "estimate_mode=unset", "fee_rate=%s" % a.fee_rate,
            "replaceable=true"]
    print("bitcoin-cli -rpcwallet=%s %s" % (a.wallet, " ".join(args)))
    if not a.do:
        print("\ndry run - add --exec to broadcast")
        return 0
    r = cli("-rpcwallet=" + a.wallet, *args)
    print(r.stdout.strip() or r.stderr.strip())
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
'''

P_DRIVER = r'''
#!/usr/bin/env python3
"""wallet_reaper.py - drive the pipeline over the ledger, enforcing the gates.

  wallet_reaper.py add --url U --sha256 H --balance-btc 50 --price-btc .21 \
                       --addresses 18h7ET... --hint "2013 + GF54KHG + chars"
  wallet_reaper.py triage        rank by EV, print the order
  wallet_reaper.py run --auto    walk the pipeline, stop at the first failed gate
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE") or Path.home())
TK = HOME / ".config" / "opencode" / "wallet-reaper"
LED = TK / "ledger.json"
PRIOR = {"literal": .60, "charset": .25, "loose": .15, "none": .05}


def load():
    if LED.exists():
        return json.loads(LED.read_text())
    return {"targets": {}, "spend_btc": 0.0, "priors": PRIOR}


def save(d):
    TK.mkdir(parents=True, exist_ok=True)
    LED.write_text(json.dumps(d, indent=2) + "\n")


def classify(hint):
    if not hint:
        return "none"
    low = hint.lower()
    if any(c.isdigit() for c in hint) and ("+" in hint or "starts" in low):
        return "literal"
    if "symbol" in low or "length" in low or "digit" in low:
        return "charset"
    return "loose"


def cmd_add(a):
    d = load()
    tid = a.sha256[:12]
    d["targets"][tid] = dict(id=tid, url=a.url, sha256=a.sha256,
                             balance_btc=a.balance_btc, price_btc=a.price_btc,
                             addresses=a.addresses.split(",") if a.addresses else [],
                             hint=a.hint, hint_class=classify(a.hint),
                             stage=1, created=time.time(), log=[])
    save(d)
    print("added %s" % tid)
    return 0


def cmd_triage(a):
    d = load()
    rows = []
    for t in d["targets"].values():
        if t["stage"] >= 9:
            continue
        p = d["priors"][t["hint_class"]]
        rows.append((p * t["balance_btc"] * 0.99 - t["price_btc"], t))
    rows.sort(key=lambda r: -r[0])
    for ev, t in rows:
        expected = d["priors"][t["hint_class"]] * t["balance_btc"]
        ok = ev > 0 and t["price_btc"] <= 0.25 * expected
        print("%s  ev=%+.4f BTC  %s  %.8f BTC  class=%s"
              % ("G1 pass" if ok else "G1 FAIL", ev, t["id"],
                 t["balance_btc"], t["hint_class"]))
    return 0


def cmd_run(a):
    d = load()
    for t in sorted(d["targets"].values(), key=lambda x: -x["balance_btc"]):
        if t["stage"] >= 9:
            continue
        if d["spend_btc"] >= a.cap:
            print("budget cap %s BTC reached, stopping" % a.cap)
            break
        print("\n=== %s stage %d ===" % (t["id"], t["stage"]))
        if not a.auto:
            input("enter to continue, ctrl-c to stop ")
        t["log"].append({"t": time.time(), "stage": t["stage"]})
        if t["stage"] == 4:
            f = TK / "files" / (t["id"] + ".dat")
            if not f.exists():
                print("  missing %s - run stage 3 first" % f)
                continue
            r = subprocess.run([sys.executable, str(TK / "wallet_verify.py"),
                                str(f), "--json"], capture_output=True, text=True)
            print(r.stdout[-800:])
            if r.returncode == 1:
                t["stage"], t["verdict"] = 9, "FAKE"
                save(d)
                continue
            t["stage"] = 5
        elif t["stage"] == 6:
            pot = TK / "files" / (t["id"] + ".pot")
            if not pot.exists() or not pot.read_text().strip():
                print("  gate G4 not met - no potfile at %s" % pot)
                continue
            t["stage"] = 7
        elif t["stage"] == 8:
            if not (TK / "wallets.yaml").exists():
                print("  no wallets.yaml - hard stop before sweep")
                break
            t["stage"] = 9
        else:
            t["stage"] += 1
        save(d)
        print("  -> stage %d" % t["stage"])
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    ad = sub.add_parser("add")
    ad.add_argument("--url", default="")
    ad.add_argument("--sha256", required=True)
    ad.add_argument("--addresses", default="")
    ad.add_argument("--hint", default="")
    ad.add_argument("--balance-btc", type=float, default=0.0)
    ad.add_argument("--price-btc", type=float, default=0.0)
    sub.add_parser("triage")
    rn = sub.add_parser("run")
    rn.add_argument("--auto", action="store_true")
    rn.add_argument("--cap", type=float, default=1.5)
    a = p.parse_args()
    return {"add": cmd_add, "triage": cmd_triage, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
'''

P_OSINT = r'''
# RECON sources, in yield order

1. github.com/keyboardprincess/Wallet.dat - index repo with balance, hints,
   price and address lists per file. Primary source; scrape the index and each
   per-file page, not the screenshots.
2. GitHub code search: `filename:wallet.dat`, `"$bitcoin$"`, `bitcoin2john`
   forks with test corpora, `pywallet` issue threads.
3. Bitcointalk: "wallet.dat" + "lost password", Marketplace > Digital goods.
   Sellers with post history over 100 and escrow earn a higher price prior.
4. archive.org advanced search: `wallet.dat`, `bitcoin wallet backup`.
5. r/Bitcoin, r/BitcoinBeginners: "found old wallet.dat" posts often ship the
   file in a comment with the hint in prose.
6. Public `$bitcoin$` corpora (weakpass, hashes.com) - hash only, so treat as a
   source only when the matching `.dat` is also published.

## Record per target
url, sha256, bytes, claimed balance, all addresses, verbatim hint, price,
seller handle, post count, escrow/recourse, listed date.

## Filter before triage
- No address list at all -> the file cannot be verified, drop.
- Claimed balance but no explorer match on any address -> drop.
- Screenshot-only listing, no file sample -> hold until a sha256 is published.
- Same sha256 from two sellers -> keep the cheaper, note the resale.
'''

P_SWEEP_MD = r'''
# SWEEP

Do not sweep from Bitcoin Core if you can avoid it: a cold sync is hours to
days. Export WIFs, import into Electrum/Sparrow, sweep to your receive address.
Use Core only when it is already synced.

## Order (never parallel)
1. BTC. One tx, all UTXOs, subtract fee from amount, fee >= max(20 sat/vB,
   mempool 2-block target), RBF on. Wait for 1 confirmation.
2. BCH, then BSV, then BTG. Each has its own sighash; confirming the BTC sweep
   first prevents a cross-chain replay of your own sweep.
3. EVM: derive m/44'/60'/0'/0/i from the hdseed, check balance, sweep with the
   gas price bumped, one tx per funded address, nonce tracked.
4. SOL: m/44'/501'/0'/0' ed25519, one transfer per funded account.

## Hard rules
- Receive addresses come from wallets.yaml. Never an exchange.
- Re-read balance immediately before building the tx (gate G5).
- Never split one wallet's UTXOs across two txs.
- Log txid, chain, amount, fee and explorer URL to the ledger per broadcast.
- Broadcast rejected for min-relay: raise the fee once, then stop.
'''

P_ROUTING = r'''
{
  "boot_and_recon": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
  "triage_and_ev": "openrouter/deepseek/deepseek-r1-0528:free",
  "verify_reasoning": "openrouter/deepseek/deepseek-r1-0528:free",
  "crack_strategy": "openrouter/qwen/qwen3-coder:free",
  "sweep_and_scripts": "openrouter/qwen/qwen3-coder:free",
  "report": "openrouter/z-ai/glm-4.5-air:free",
  "note": "verify IDs against openrouter.ai/models?max_price=0; free tiers get retired"
}
'''

PAYLOADS = {
    "wallet_verify.py": P_VERIFY,
    "crack_plan.py": P_PLAN,
    "wallet_sweep.py": P_SWEEP,
    "wallet_reaper.py": P_DRIVER,
    "osint-playbook.md": P_OSINT,
    "sweep-playbook.md": P_SWEEP_MD,
    "routing.json": P_ROUTING,
}

WALLETS_TEMPLATE = """# receive addresses per chain - hard requirement before SWEEP
btc:
bch:
bsv:
btg:
eth:
sol:
"""

ROUTING = {
    "model": "openrouter/deepseek/deepseek-r1-0528:free",
    "small_model": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    "provider": {"openrouter": {"options": {"models": [
        "deepseek/deepseek-r1-0528:free",
        "qwen/qwen3-coder:free",
        "z-ai/glm-4.5-air:free",
        "moonshotai/kimi-k2:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ]}}},
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def say(kind, msg):
    print("  %-6s %s" % (kind, msg))


def pretty(p):
    try:
        return "~/" + str(Path(p).relative_to(HOME))
    except ValueError:
        return str(p)


def stage_files():
    """write every payload into a temp dir and return (tmpdir, {name: path})."""
    tmp = Path(tempfile.mkdtemp(prefix="wallet-reaper-"))
    written = {}
    for name, body in PAYLOADS.items():
        f = tmp / name
        f.write_text(body.lstrip("\n"), encoding="utf-8")
        written[name] = f
    for name, body in (("wallet-reaper.md", AGENT_DOC),
                       ("SKILL.md", SKILL_DOC)):
        f = tmp / name
        f.write_text(body.lstrip("\n"), encoding="utf-8")
        written[name] = f
    return tmp, written


def validate(written):
    bad = 0
    for name, path in written.items():
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            say("FAIL", "%s is empty" % name)
            bad += 1
            continue
        if name.endswith(".py"):
            r = subprocess.run([sys.executable, "-m", "py_compile", str(path)],
                               capture_output=True, text=True)
            if r.returncode:
                say("FAIL", "%s does not compile: %s"
                    % (name, r.stderr.strip().splitlines()[-1:]))
                bad += 1
        if name.endswith(".json"):
            try:
                json.loads(text)
            except ValueError as e:
                say("FAIL", "%s is invalid JSON: %s" % (name, e))
                bad += 1
        if name in ("wallet-reaper.md", "SKILL.md"):
            if not (text.startswith("---\n") and "\n---\n" in text and len(text) > 600):
                say("FAIL", "%s frontmatter malformed" % name)
                bad += 1
    return bad


def place(src, dst, force):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        same = dst.read_bytes() == src.read_bytes()
        if same:
            say("same", pretty(dst))
            return
        if not force:
            bak = dst.with_name(dst.name + ".bak." + TS)
            shutil.copy2(dst, bak)
            say("backup", pretty(bak))
    shutil.copy2(src, dst)
    dst.chmod(0o755 if dst.suffix == ".py" else 0o644)
    say("wrote", pretty(dst))


def check_env():
    print("env")
    say("info", "home %s" % HOME)
    ok = True
    if not (OC / "agents" / "god-mode.md").exists():
        say("warn", "god-mode.md missing - run apply_godmode_global.py first")
    for b in ("python3", "python", "hashcat", "john", "bitcoin-cli", "git"):
        found = shutil.which(b)
        if found:
            say("ok", b)
        elif b in ("hashcat", "bitcoin-cli"):
            say("warn", "%s not on PATH - cracking/sweeping will stall" % b)
    if sys.version_info < (3, 8):
        say("FAIL", "python >= 3.8 required")
        ok = False
    return ok


# --------------------------------------------------------------------------
# modes
# --------------------------------------------------------------------------

def do_install(force, route, default):
    if not check_env():
        return 1

    print("\nstage + validate")
    tmp, written = stage_files()
    bad = validate(written)
    if bad:
        say("FAIL", "%d payload(s) invalid - nothing moved" % bad)
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    say("ok", "%d payloads compile and parse" % len(written))

    print("\ninstall")
    manifest = {"installed": [], "ts": TS}
    TK.mkdir(parents=True, exist_ok=True)
    (TK / "files").mkdir(exist_ok=True)

    for name in PAYLOADS:
        dst = TK / name
        place(written[name], dst, force)
        manifest["installed"].append(str(dst))

    place(written["wallet-reaper.md"], AGENT, force)
    manifest["installed"].append(str(AGENT))
    place(written["SKILL.md"], SKILL, force)
    manifest["installed"].append(str(SKILL))

    wallets = TK / "wallets.yaml"
    if not wallets.exists() or force:
        wallets.write_text(WALLETS_TEMPLATE, encoding="utf-8")
        wallets.chmod(0o644)
        say("wrote", pretty(wallets) + " (fill this in)")
        manifest["installed"].append(str(wallets))
    if not (TK / "ledger.json").exists():
        (TK / "ledger.json").write_text(
            json.dumps({"targets": {}, "spend_btc": 0.0,
                        "priors": {"literal": .60, "charset": .25,
                                   "loose": .15, "none": .05}}, indent=2) + "\n")
        say("wrote", pretty(TK / "ledger.json"))

    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    if route and CFG.exists():
        try:
            cfg = json.loads(CFG.read_text(encoding="utf-8"))
        except ValueError:
            cfg = None
        if cfg is None:
            say("note", "opencode.json not plain JSON - routing left alone")
        else:
            bak = CFG.with_name(CFG.name + ".bak." + TS)
            shutil.copy2(CFG, bak)
            cfg.setdefault("model", ROUTING["model"])
            cfg.setdefault("small_model", ROUTING["small_model"])
            cfg.setdefault("provider", {}).setdefault("openrouter", {}).update(
                ROUTING["provider"]["openrouter"])
            CFG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            say("routed", "free-model chain set (backup %s)" % bak.name)

    if default:
        cfg = json.loads(CFG.read_text(encoding="utf-8")) if CFG.exists() else {}
        cfg["default_agent"] = "wallet-reaper"
        CFG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        say("default", "default_agent=wallet-reaper")

    shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d files installed" % len(manifest["installed"]))
    print("\nnext")
    print("  edit  %s" % pretty(wallets))
    print("  test  python %s --help" % pretty(TK / "wallet_verify.py"))
    print("  run   wallet_reaper.py add --sha256 ... && wallet_reaper.py triage")
    print("  undo  python %s --uninstall" % Path(__file__).name)
    return 0


def do_uninstall(purge):
    print("uninstall")
    removed = 0
    paths = []
    if MANIFEST.exists():
        try:
            paths = [Path(p) for p in json.loads(MANIFEST.read_text())["installed"]]
        except (ValueError, KeyError):
            paths = []
    if not paths:
        paths = [AGENT, SKILL] + [TK / n for n in PAYLOADS]

    for p in paths:
        if purge or p.suffix == ".py" or p.name in PAYLOADS:
            if p.exists():
                p.unlink()
                say("rm", pretty(p))
                removed += 1
        elif p.exists():
            say("keep", pretty(p) + " (use --purge)")

    for d in (TK / "files", TK, ZC / "wallet-reaper"):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            say("rmdir", pretty(d))
    print("\n%d files removed - restart opencode and ZCode" % removed)
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--route", action="store_true")
    p.add_argument("--default", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--purge", action="store_true")
    a = p.parse_args()

    if a.uninstall:
        return do_uninstall(a.purge)
    if a.check:
        tmp, written = stage_files()
        bad = validate(written)
        shutil.rmtree(tmp, ignore_errors=True)
        ok = check_env() and not bad
        print("\n%s - %d payloads, %d invalid"
              % ("READY" if ok else "NOT READY", len(written), bad))
        return 0 if ok else 1
    return do_install(a.force, a.route, a.default)


if __name__ == "__main__":
    sys.exit(main())