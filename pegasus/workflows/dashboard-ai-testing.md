# Dashboard: AI Testing / Inference / Fine-Tuning / Evaluation (Defensive — H)
# Source: pegasus/modules/ai/ (backends, catalog, chain, routes, providers, validator), pegasus/modules/learn/ (finetune, bandit, gate, preferences), pegasus/core/plugin/__init__.py (AppContext)
# Purpose: Monitor AI model health, inference latency, evaluation scores, fine-tuning progress — defensive auditing of AI pipeline; no offensive model training
# Features mapped: 61 FULL + AI catalog + crypto_selftest + payload DNA / mutation / bind + Q9 header embedded
# Alert: /api/logs (category: ai_testing) + evidence to /log/events.jsonl + reports_dir (get_reports_dir)
# Default settings: ai_monitor_enabled=true; inference_latency_threshold=500ms; evaluation_score_target=0.85; finetune_safe_only=true (no offensive fine-tuning)
# Configurable: yes — via AppShell/footer settings + status-config.json extension; model registry (pegasus/modules/ai/catalog.py)
# Status: FULL defensive — AI pipeline monitoring; offensive AI weaponization excluded per policy
# Reverse engineering / audit: reads ai/catalog.py + learn/gate.py + crypto_selftest results to generate defensive AI-health reports (no execution of malicious prompts)
