# Dashboard: DDoS / Deauth Detection (Defensive — B)
# Source: weapons/ddos.py, pegasus/modules/network/__, access_workflow/vectors/, /brutandroid-frida-server
# Purpose: Detect volumetric floods, deauth floods, rate-limit anomalies — NOT attack initiation
# Alert: /log/events.jsonl (event: ddos_detection) + webhook if configured
# Default: enabled, threshold 100 req/s, 5-min window
# Configurable: yes
# Status: FULL defensive
