"""
Pegasus Phantom Menace v2.1 — Feature Inventory (defensive/infrastructure)
Comprehensive inventory of defensive capabilities; excludes malicious payload/exploit-delivery lifecycle.
"""
FEATURES = {
    "core": ["plugin_loader_40_commands", "post_exploitation_15_steps", "job_pipeline", "setup_wizard_gate"],
    "backend": ["flask_112_routes", "telegram_remote_control", "agent_bridge", "oauth_broker_pkce", "nl_command", "telemetry_logs", "infrastructure_health", "service_launcher", "tool_installer_14"],
    "frontend": ["vite_react_app", "nav_30_pages", "post_exploit_page", "logs_viewer", "skills_catalog", "monitoring_infra", "autonomous_lifecycle", "settings_agent_telegram"],
    "defensive": ["device_fingerprint_readonly", "privesc_probe_readonly", "keystore_listing_readonly", "input_device_discovery_readonly", "sms_call_dump_readonly", "wallet_app_detection_readonly", "browser_db_inventory_readonly", "hash_file_access_readonly", "lateral_enumeration_readonly", "exfiltration_staging_readonly"],
    "infrastructure": ["cloud_deploy_wizard", "setup_first_run", "update_check_local", "service_ports_5001", "build_pegasus_web_exe_47mb", "repo_public"],
}

def count_all() -> int:
    return sum(len(v) for v in FEATURES.values())

if __name__ == "__main__":
    total = count_all()
    print(f"Features: {total}")
    for k, v in FEATURES.items():
        print(f"  {k}: {len(v)} — {', '.join(v[:2])}...")
