# Pegasus agent skills

Canonical instructions. The five adapter directories are generated from
`skills/agents.yaml`; never hand-edit them.

Rule: agent files orchestrate, scripts enforce. Every command wraps a target
that fails loudly.

Three invariants bind every skill here: capability over platform, leases over
sequencing, derived over declared.
