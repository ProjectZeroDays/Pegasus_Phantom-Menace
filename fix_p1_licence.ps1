# fix_p1_licence.ps1 — proprietary LICENSE, decision record, P1/R0 precondition patch
$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.git')) { throw 'run from the repo root' }
$root = Get-Location
$utf8 = New-Object System.Text.UTF8Encoding($false)

# --- 1. LICENSE ---------------------------------------------------------
$lic = @(
'Pegasus v2.1.0',
'Created by ProjectZeroDays',
'',
'Copyright (c) 2025 ProjectZeroDays. All rights reserved.',
'',
'This software, together with its associated documentation, assets and generated',
'artifacts (the "Software"), is proprietary. It is not free software and not open',
'source. No licence is granted by default, and use without permission is unlawful.',
'',
'1. PERMISSION REQUIRED',
'   Any use of the Software requires prior written permission from the copyright',
'   holder. Absent that permission, use, copying, modification or distribution is',
'   unauthorised and infringes copyright.',
'',
'2. SCOPE OF ANY GRANT',
'   Permission, where granted, is limited to the terms stated in the grant.',
'   Rights not expressly granted are reserved. No permission extends to',
'   commercial use, redistribution, sublicensing, or hosting as a service unless',
'   the grant says so in writing.',
'',
'3. MODIFICATION AND LIKENESS',
'   Modification is permitted only with prior written permission. Any modified or',
'   derivative version must remain in the likeness of the original:',
'',
'   a. the name "Pegasus" and the ProjectZeroDays attribution must be retained',
'      and presented with equal prominence;',
'   b. the version lineage must be recorded, naming the version derived from;',
'   c. the derivative must not be rebranded, renamed, or presented as an',
'      independent work;',
'   d. divergent forks, where permitted, must be identified as forks.',
'',
'4. ATTRIBUTION',
'   Every copy, deployment and derivative must carry credit to the original',
'   author ("ProjectZeroDays") and a link to the official channel:',
'   <INSERT OFFICIAL YOUTUBE URL>',
'',
'5. NO WARRANTY',
'   The Software is provided "as is", without warranty of any kind, express or',
'   implied, including but not limited to the warranties of merchantability,',
'   fitness for a particular purpose and noninfringement.',
'',
'6. NO LIABILITY',
'   In no event shall the author or copyright holder be liable for any claim,',
'   damages or other liability, whether in an action of contract, tort or',
'   otherwise, arising from, out of or in connection with the Software or the use',
'   or other dealings in the Software.',
'',
'7. TERMINATION',
'   Permission terminates automatically on breach of these terms. On termination',
'   all copies must be destroyed or returned, and continued use becomes',
'   unauthorised.',
'',
'8. RESERVATION',
'   These terms state obligations on the user only. They do not themselves grant',
'   permission to use the Software.',
'',
'By using the Software you agree to these terms.'
) -join "`r`n"
[IO.File]::WriteAllText((Join-Path $root 'LICENSE'), $lic + "`r`n", $utf8)
Write-Host 'wrote LICENSE'

# --- 2. decision record -------------------------------------------------
New-Item -ItemType Directory -Force docs | Out-Null
$dec = @(
'# Licence decision',
'',
'Status: decided',
'Date: 2026-11-02',
'Supersedes: permissive educational/research grant (v1.1)',
'',
'## Decision',
'',
'Pegasus is proprietary. All rights reserved. Use requires prior written',
'permission; unauthorised use is unlawful. Modification is permitted only with',
'permission and only where the derivative remains in the likeness of the',
'original (name, attribution and lineage retained; no rebranding).',
'',
'## Rejected',
'',
'**MIT / Apache-2.0.** Both grant unrestricted use, modification and',
'redistribution outright, including commercially, with no way to recall them. For',
'a tool aimed at government sale, that gives away the distribution rights that',
'are the product.',
'',
'**Permissive-with-attribution (the v1.1 text).** Retained credit and a channel',
'link, but still granted free use to anyone for education and research. It read',
'as open source and was routinely treated as such. It also left modification',
'unconstrained, so a rebranded fork was permitted.',
'',
'## Consequences',
'',
'- Distribution is controlled. Buyers get a grant, not a copy of rights.',
'- No OSI-compliant modification freedom; the likeness clause is the blocker.',
'- Contribution needs a grant in place before patches are accepted.',
'- Credit and the channel link are contractual, not advisory.',
'',
'## Open items',
'',
'- Official YouTube URL to be inserted at clause 4.',
'- Grant template for buyers not yet written.',
'- Review if a commercial offering needs redistribution rights.'
) -join "`r`n"
[IO.File]::WriteAllText((Join-Path $root 'docs\LICENSE-DECISION.md'), $dec + "`r`n", $utf8)
Write-Host 'wrote docs\LICENSE-DECISION.md'

# --- 3. patch bootstrap.py ---------------------------------------------
$bpPath = Join-Path $root 'bootstrap.py'
$bp = [IO.File]::ReadAllText($bpPath)

$oldP1 = '  - {id: P1, gate: G2, revert: "git revert", requires: [{path: docs/HANDOFF.md}], produces: []}'
$newP1 = '  - {id: P1, gate: G2, revert: "git revert", requires: [{path: docs/HANDOFF.md}, {path: LICENSE}, {path: docs/LICENSE-DECISION.md}], produces: []}'
$oldR0 = '    requires_empty: [build/map.diff], produces: [build/map.diff]}'
$newR0 = '    produces: [build/map.diff]}'

foreach ($pair in @(@($oldP1, $newP1), @($oldR0, $newR0))) {
    $hits = ([regex]::Matches($bp, [regex]::Escape($pair[0]))).Count
    if ($hits -ne 1) { throw "expected 1 match, got $hits for: $($pair[0])" }
    $bp = $bp.Replace($pair[0], $pair[1])
}
[IO.File]::WriteAllText($bpPath, $bp, $utf8)
Write-Host 'patched bootstrap.py (P1 now requires LICENSE + decision record, R0 requires_empty removed)'

# --- 4. regenerate ------------------------------------------------------
python bootstrap.py --force
if ($LASTEXITCODE -ne 0) { throw "bootstrap --force failed: $LASTEXITCODE" }

# --- 5. verify ----------------------------------------------------------
python scripts/require.py --lint
if ($LASTEXITCODE -ne 0) { throw "phase lint failed: $LASTEXITCODE" }
python scripts/require.py P1
if ($LASTEXITCODE -ne 0) { throw "P1 still refusing: $LASTEXITCODE" }

Write-Host ''
Write-Host '--- first bytes ---'
python -c "print(repr(open('LICENSE',encoding='utf-8').read()[:40]))"
python -c "print(repr(open('docs/LICENSE-DECISION.md',encoding='utf-8').read()[:40]))"

Write-Host ''
Write-Host '--- phases ---'
python -c "import yaml,json;d=yaml.safe_load(open('build/phases.yaml',encoding='utf-8'));print(json.dumps([p for p in d['phases'] if p['id'] in ('P1','R0')],indent=2))"

Write-Host ''
Write-Host '--- content spot-checks ---'
cmd /c findstr /n /c:"v2.1.0" /c:"unlawful" LICENSE
cmd /c findstr /n /c:"Supersedes" docs\LICENSE-DECISION.md
git status --short