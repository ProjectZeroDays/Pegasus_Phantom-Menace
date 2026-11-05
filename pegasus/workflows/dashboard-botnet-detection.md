# Dashboard: Botnet Detection / C2 Monitoring (Defensive — A)
# Source: pegasus/modules/social_media/social_server.py, pegasus/modules/relay/relay_server.py, weapons/botnet.py
# Purpose: Detect C2 beacons, botnet command patterns, unauthorized relay connections
# Features mapped: 55-61 (payload delivery, C2, botnet), relay routes, monitoring
# Alert: /api/logs (category: botnet_detection) + telemetry event
# Default settings: enabled, 30s beacon interval, auto-log on unknown relay IP
# Configurable: yes — via settings / status-config.json
# Status: FULL — defensive monitoring only; offensive C2 not implemented
