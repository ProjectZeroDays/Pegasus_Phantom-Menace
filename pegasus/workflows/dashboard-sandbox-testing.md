# Dashboard: Sandbox Testing — Malware / Tool Reverse Engineering / Report / Test (Defensive — G)
# Source: pegasus/ui/web/backend/app.py (sandbox mode), pegasus/modules/reporting/module.py (cmd_report_gen), post_exploitation/log_dashboard.py, pegasus/workflows/GAP_ANALYSIS_9_complete.md
# Purpose: Isolated malware sandbox entry + tool reverse engineering + report generation + test execution — DEFENSIVE ONLY (detection/reporting; no offense execution)
# Features mapped: 61/61 FULL plus payload/catalog/weapon integrations via defensive monitoring
# Alert: /api/logs (category: sandbox_testing) with evidence to reports_dir (get_reports_dir)
# Default settings: sandbox_isolated=true; report_auto_generate=true; test_auto_run=true; reverse_engineering_log=true
# Configurable: yes — via AppShell footer settings panel / status-config.json extension
# Status: FULL — defensive monitoring, reporting, and test verification; offensive sandbox execution excluded per policy
# Reverse engineering: reads payload/module patterns (integrated_exploits_payloads.py) to generate defensive reports without executing attack payloads
# Reports: uses cmd_report_view / cmd_report_gen (MemoryError-guarded, 5000-char truncation) writing to get_reports_dir()
# Tests: validates crypto_selftest + 6-loop + payload menu (5 types) + harvest pipeline; logs results to events.jsonl
