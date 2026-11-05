# Dashboard: Brute-Force Detection / Vault Protection (Defensive — D)
# Source: pegasus/modules/passgen/, pegasus/modules/auth/, weapons/crack/, access_workflow/frp_unlock.py, payload/catalog CVEs
# Purpose: Detect failed-login anomalies, weak-password patterns, vault access attempts; protect crypto wallets via monitoring (NOT cracking)
# Alert: /api/logs (brute_force_detection) + vault access pattern log
# Default: enabled, 5 failed attempts = alert, wallet.dat exposure detection active
# Configurable: yes — thresholds, vault paths, crypto-monitor list
# Status: FULL defensive; offensive brute-force excluded
