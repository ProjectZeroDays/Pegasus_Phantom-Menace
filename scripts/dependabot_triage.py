"""Triage Dependabot alerts: group the criticals by manifest and ecosystem.

PowerShell mangles `gh api --jq`, so all filtering happens in Python.
Read-only: this produces a triage plan, it changes nothing.
"""
import collections
import json
import subprocess
import sys

REPO = 'repos/ProjectZeroDays/Pegasus_Phantom-Menace/dependabot/alerts'
# The API reports 'medium', not 'moderate' - the web banner's wording differs
# from the field value, which is why 212 alerts previously fell into 'other'.
SEVERITIES = ('critical', 'high', 'medium', 'low')
# Lockfiles can be regenerated wholesale; these are the batch-safe surfaces.
LOCK_NAMES = ('package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'uv.lock',
              'poetry.lock', 'Pipfile.lock', 'requirements.txt',
              'Cargo.lock', 'go.sum', 'composer.lock')
# Vendored third-party trees: their alerts are real but the fix is a vendoring
# decision, not a bump, so they are reported separately from first-party risk.
VENDORED_MARKERS = ('weapons/',)


def fetch_all() -> list:
    """gh api rejects an explicit `page` param; use its own --paginate.

    --paginate emits each page's JSON document back-to-back, so the output is
    not a single valid JSON value. Decode successive documents with raw_decode.
    """
    url = f'{REPO}?state=open&per_page=100'
    # text=True alone decodes with the locale codec (cp1252) and dies on
    # non-cp1252 bytes in advisory text; force utf-8 and tolerate strays.
    proc = subprocess.run(['gh', 'api', '--paginate', url],
                          capture_output=True, text=True, timeout=600,
                          encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        print(f'gh api failed: {(proc.stderr or "")[:500]}')
        return []
    text = proc.stdout or ''
    if not text.strip():
        print('gh api returned empty stdout')
        return []
    decoder = json.JSONDecoder()
    idx = 0
    alerts = []
    n = len(text)
    while idx < n:
        while idx < n and text[idx] in ' \r\n\t':
            idx += 1
        if idx >= n:
            break
        try:
            value, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError as exc:
            print(f'parse stop at {idx}: {exc}')
            print('context:', repr(text[idx:idx + 160]))
            break
        idx = end
        if isinstance(value, list):
            alerts.extend(value)
        elif isinstance(value, dict):
            alerts.append(value)
    return alerts


def _fields(a: dict) -> tuple:
    """Normalize one alert into the fields the triage prints."""
    sv = a.get('security_vulnerability') or {}
    adv = a.get('security_advisory') or {}
    dep = a.get('dependency') or {}
    pkg = sv.get('package') or dep.get('package') or {}
    fixed = sv.get('first_patched_version') or {}
    fix_id = fixed.get('identifier') if isinstance(fixed, dict) else fixed
    manifest = dep.get('manifest_path') or '?'
    return {
        'name': pkg.get('name') or '?',
        'eco': pkg.get('ecosystem') or '?',
        'manifest': manifest,
        'range': sv.get('vulnerable_version_range') or '',
        'fix': fix_id or None,
        'id': adv.get('cve_id') or adv.get('ghsa_id') or '?',
        'sev': adv.get('severity') or '?',
        'bumpable': bool(fix_id),
        'lockfile': any(n in manifest for n in LOCK_NAMES),
    }


def _is_vendored(manifest: str) -> bool:
    return any(manifest.startswith(m) or f'/{m}' in manifest for m in VENDORED_MARKERS)


try:
    from packaging.version import Version as _PkgVersion
    from packaging.version import InvalidVersion as _InvalidVersion
except Exception:  # pragma: no cover - packaging is normally present
    _PkgVersion = None
    _InvalidVersion = ValueError


def _vkey(v: str):
    """Sort key for a version string.

    Lexicographic comparison is wrong for multi-digit components: as strings
    '3.9.4' > '3.10.3', which made the earlier run report nltk -> 3.9.4 when
    3.10.3 is the real highest patched version. Prefer packaging.version and
    fall back to a numeric-tuple key that still orders 3.10.3 above 3.9.4.
    """
    if not v:
        return (0, ())
    if _PkgVersion is not None:
        try:
            return (1, _PkgVersion(v))
        except _InvalidVersion:
            pass
    parts = []
    for chunk in str(v).replace('-', '.').split('.'):
        digits = ''.join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return (0, tuple(parts))


def _canon(name: str) -> str:
    """Case-fold a package name so GitPython/gitpython/Gitpython collapse.

    Ecosystems differ on normalization (PEP 503 folds case and separators for
    pip; npm is case-sensitive in practice), so this is a reporting aid: it
    merges advisory rows that clearly name one package. The per-ecosystem
    normalized name is printed alongside when it differs.
    """
    return (name or '').strip().lower()


def _print_group(label: str, rows: list) -> None:
    print(f'\n--- {label}: {len(rows)} alerts ---')
    # Distinct packages, case-folded so GitPython/gitpython/Gitpython collapse.
    raw_names = {r['name'] for r in rows}
    canon = collections.defaultdict(set)
    for r in rows:
        canon[_canon(r['name'])].add(r['name'])
    print(f'  distinct packages: {len(canon)} '
          f'(from {len(raw_names)} raw spellings)')
    merged = {k: v for k, v in canon.items() if len(v) > 1}
    if merged:
        print('  case-variant spellings merged:')
        for k in sorted(merged):
            print(f'    {k}: {", ".join(sorted(merged[k]))}')
    print(f'  bumpable (patched version known): '
          f'{sum(1 for r in rows if r["bumpable"])}')
    print(f'  no patch (needs review/ignore/mitigation): '
          f'{sum(1 for r in rows if not r["bumpable"])}')
    print(f'  lockfile-backed (batch-safe): {sum(1 for r in rows if r["lockfile"])}')
    print(f'  source-level (hand-edit manifest): '
          f'{sum(1 for r in rows if not r["lockfile"])}')
    print(f'  by severity: '
          f'{dict(collections.Counter(r["sev"] for r in rows))}')
    # The concrete bump list: highest patched version per package, ranked with
    # a version-aware key rather than lexicographically.
    print('  packages needing a bump (highest patched version wins):')
    best: dict[str, str] = {}
    for r in rows:
        if not (r['bumpable'] and r['fix']):
            continue
        key = _canon(r['name'])
        if key not in best or _vkey(r['fix']) > _vkey(best[key]):
            best[key] = r['fix']
    for name in sorted(best):
        print(f'    {name:32} -> {best[name]}')
    # A package can carry both patched and unpatched advisories, so report
    # no-patch packages separately from whether they are bumpable overall.
    unpatched = sorted({_canon(r['name']) for r in rows if not r['bumpable']})
    if unpatched:
        both = sorted(set(unpatched) & set(best))
        print(f'  packages with >=1 NO-PATCH advisory: {", ".join(unpatched)}')
        if both:
            print(f'    of these, partly bumpable (mixed advisories): '
                  f'{", ".join(both)}')
        pure = sorted(set(unpatched) - set(best))
        if pure:
            print(f'    entirely unpatched (needs ignore/mitigation): '
                  f'{", ".join(pure)}')


def main() -> int:
    alerts = fetch_all()

    print(f'total open alerts fetched: {len(alerts)}')
    if not alerts:
        print('NO_ALERTS_FETCHED - cannot triage')
        return 1

    by_sev = collections.Counter()
    for a in alerts:
        sev = (a.get('security_advisory') or {}).get('severity') or 'unknown'
        by_sev[sev] += 1
    print('by severity:', {s: by_sev.get(s, 0) for s in SEVERITIES},
          '| other:', sum(v for k, v in by_sev.items() if k not in SEVERITIES))

    criticals = [a for a in alerts
                 if (a.get('security_advisory') or {}).get('severity') == 'critical']
    print(f'\ncritical alerts: {len(criticals)}')

    # Group by (ecosystem, manifest) so lockfile-only bumps can be batched.
    groups = collections.defaultdict(list)
    for a in criticals:
        pkg = a.get('security_vulnerability') or {}
        dep = (a.get('dependency') or {})
        manifest = dep.get('manifest_path') or '?'
        eco = (dep.get('package') or {}).get('ecosystem') or pkg.get('package', {}).get('ecosystem') or '?'
        groups[(eco, manifest)].append(a)

    print('\n=== criticals grouped by ecosystem + manifest ===')
    for (eco, manifest), rows in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f'\n[{eco}] {manifest}  ({len(rows)} alerts)')
        for a in sorted(rows, key=lambda r: (r.get('security_vulnerability') or {}).get('package', {}).get('name', '')):
            sv = a.get('security_vulnerability') or {}
            adv = a.get('security_advisory') or {}
            name = (sv.get('package') or {}).get('name') or '?'
            vuln_range = sv.get('vulnerable_version_range') or ''
            fixed = sv.get('first_patched_version') or {}
            fix_id = fixed.get('identifier') if isinstance(fixed, dict) else fixed
            cve = adv.get('cve_id') or adv.get('ghsa_id') or '?'
            print(f'  {name:34} {vuln_range:28} -> fix {fix_id or "NONE":18} {cve}')

    # Actionability split across every alert, using the normalized fields.
    allrows = [_fields(a) for a in alerts]
    print(f'\n=== all {len(allrows)} alerts: actionability split ===')
    print(f'has a patched version (bumpable): {sum(1 for r in allrows if r["bumpable"])}')
    print(f'no patched version (needs review/vendoring): '
          f'{sum(1 for r in allrows if not r["bumpable"])}')
    print(f'lockfile-backed (batch-safe): {sum(1 for r in allrows if r["lockfile"])}')
    print(f'source-level (hand-edit manifest): '
          f'{sum(1 for r in allrows if not r["lockfile"])}')

    crit_rows = [_fields(a) for a in criticals]
    print(f'\nlockfile-backed CRITICAL groups: '
          f'{sum(1 for r in crit_rows if r["lockfile"])} of {len(crit_rows)}')
    for (eco, manifest), rows in sorted(groups.items()):
        tag = 'lockfile' if any(n in manifest for n in LOCK_NAMES) else 'source'
        print(f'  [{eco}] {manifest}: {len(rows)} ({tag})')

    # ---- vendored vs first-party split -------------------------------------
    # Vendored third-party trees carry real alerts, but the fix is a vendoring
    # decision (re-vendor / ignore / delete), not a dependency bump. First-party
    # manifests ship in the installer and can be bumped immediately.
    vendored = [r for r in allrows if _is_vendored(r['manifest'])]
    first_party = [r for r in allrows if not _is_vendored(r['manifest'])]
    print(f'\n=== provenance split ===')
    print(f'vendored (weapons/*):   {len(vendored)} alerts '
          f'({round(100 * len(vendored) / len(allrows), 1)}% of total)')
    print(f'first-party:            {len(first_party)} alerts')
    print(f'first-party by severity: '
          f'{dict(collections.Counter(r["sev"] for r in first_party))}')

    print('\n' + '=' * 72)
    print('FIRST-PARTY TRIAGE - actionable now, no vendoring decision needed')
    print('=' * 72)
    by_manifest = collections.defaultdict(list)
    for r in first_party:
        by_manifest[r['manifest']].append(r)
    # Highest severity first, then largest manifest first.
    sev_rank = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    for manifest, rows in sorted(
            by_manifest.items(),
            key=lambda kv: (min(sev_rank.get(r['sev'], 9) for r in kv[1]),
                            -len(kv[1]), kv[0])):
        eco = rows[0]['eco']
        kind = 'lockfile' if rows[0]['lockfile'] else 'source-level'
        _print_group(f'[{eco}] {manifest} ({kind})', rows)

    print('\n' + '=' * 72)
    print('VENDORED TRIAGE - blocked on a vendoring decision, not a bump')
    print('=' * 72)
    v_by_manifest = collections.defaultdict(list)
    for r in vendored:
        v_by_manifest[r['manifest']].append(r)
    for manifest, rows in sorted(v_by_manifest.items(),
                                 key=lambda kv: -len(kv[1])):
        _print_group(f'[{rows[0]["eco"]}] {manifest}', rows)

    return 0


if __name__ == '__main__':
    sys.exit(main())
