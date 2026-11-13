"""What do the electron advisories actually require? Facts before any bump."""
import collections
import json
import subprocess

REPO = 'repos/ProjectZeroDays/Pegasus_Phantom-Menace/dependabot/alerts'


def fetch_all():
    proc = subprocess.run(['gh', 'api', '--paginate', f'{REPO}?state=open&per_page=100'],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=600)
    text = proc.stdout or ''
    dec = json.JSONDecoder()
    i, out = 0, []
    while i < len(text):
        while i < len(text) and text[i] in ' \r\n\t':
            i += 1
        if i >= len(text):
            break
        v, i = dec.raw_decode(text, i)
        out.extend(v) if isinstance(v, list) else out.append(v)
    return out


alerts = fetch_all()
print(f'total open: {len(alerts)}')

# Everything about the electron package, across both first-party manifests.
rows = []
for a in alerts:
    sv = a.get('security_vulnerability') or {}
    dep = a.get('dependency') or {}
    pkg = sv.get('package') or dep.get('package') or {}
    if (pkg.get('name') or '').lower() != 'electron':
        continue
    adv = a.get('security_advisory') or {}
    fixed = sv.get('first_patched_version') or {}
    rows.append({
        'manifest': dep.get('manifest_path'),
        'sev': adv.get('severity'),
        'range': sv.get('vulnerable_version_range'),
        'fix': (fixed.get('identifier') if isinstance(fixed, dict) else fixed),
        'id': adv.get('cve_id') or adv.get('ghsa_id'),
    })

print(f'electron alerts: {len(rows)}')
print('\nby manifest:', dict(collections.Counter(r['manifest'] for r in rows)))
print('by severity:', dict(collections.Counter(r['sev'] for r in rows)))

print('\n=== distinct vulnerable ranges and their first patched version ===')
seen = collections.Counter()
for r in rows:
    seen[(r['range'], r['fix'])] += 1
for (rng, fix), n in sorted(seen.items(), key=lambda kv: (kv[0][1] or '')):
    print(f'  x{n:<3} vulnerable {str(rng):26} -> first patched {fix}')

# The binding constraint: to clear EVERY electron advisory you need a version
# at or above the highest first_patched_version.
fixes = [r['fix'] for r in rows if r['fix']]
print(f'\nalerts with a patch: {len(fixes)} of {len(rows)}')
print(f'alerts with NO patch: {len(rows) - len(fixes)}')

try:
    from packaging.version import Version
    hi = max(Version(f) for f in fixes)
    print(f'HIGHEST first_patched_version (the binding target): {hi}')
    lo = min(Version(f) for f in fixes)
    print(f'lowest  first_patched_version: {lo}')
except Exception as exc:
    print('packaging unavailable:', exc)

# How many alerts would a modest 31.x bump clear vs a jump to the highest?
print('\n=== what each candidate target would clear ===')
for cand in ('31.7.7', '33.4.11', '37.10.3', '42.11.16'):
    try:
        c = Version(cand)
    except Exception:
        continue
    cleared = sum(1 for r in rows if r['fix'] and Version(r['fix']) <= c)
    print(f'  electron >= {cand:10} clears {cleared:3} of {len(rows)} electron alerts')
