# Dashboard: Sandboxed Ransomware Detection (Defensive — F)
# Source: weapons/ransomware.py, pegasus/modules/delivery/, post_exploitation/log_dashboard.py, sandbox diagnostics
# Purpose: Malware sandbox entry, detect encryption patterns, persistent file writes, C2 beacon after payload — NOT execute attack
# Alert: /api/logs (ransomware_sandbox) + evidence path to reports dir (get_reports_dir)
# Default: enabled, sandbox isolated, auto-report on detection
# Configurable: yes — sandbox mode (isolated/hosted), report destination
# Status: FULL defensive; offensive ransomware excluded per policy
