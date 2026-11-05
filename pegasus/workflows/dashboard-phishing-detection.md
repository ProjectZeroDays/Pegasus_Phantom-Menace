# Dashboard: Phishing / Social Engineering Detection (Defensive — C)
# Source: pegasus/modules/delivery/ (slack/discord/telegram/teams/whatsapp), access_workflow/agent/factory, email_vector.py, messaging_vector.py
# Purpose: URL scanning, email header analysis, social-media message analysis for phishing patterns
# Alert: /api/logs (phishing_detection) + evidence to /log/events.jsonl
# Default: enabled, 100 URL/day scan limit, block suspicious domains
# Configurable: yes
# Status: FULL defensive
