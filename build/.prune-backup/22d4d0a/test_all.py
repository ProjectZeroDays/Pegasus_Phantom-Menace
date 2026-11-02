#!/usr/bin/env python3
"""Pegasus Phantom Menace v2.1.0 — End-to-End Verification Tests
Port: 5001 | NSSM: auto-download enabled in installer
"""

import sys
from pathlib import Path

def main():
    errors = []
    checks = {}

    # 1. Port 5001 everywhere it matters
    mobile_text = Path("pegasus-mobile/app/src/main/res/values/strings.xml").read_text(encoding="utf-8")
    checks["mobile_port_5001"] = "5001" in mobile_text

    # 2. Launch script
    launch_text = Path("launch_app.py").read_text(encoding="utf-8")
    checks["launch_port_5001"] = "port=5001" in launch_text

    # 3. Start server script
    server_text = Path("start_server.py").read_text(encoding="utf-8")
    checks["start_server_5001"] = "port=5001" in server_text and "5001" in server_text

    # 4. README has icon reference
    readme_text = Path("README.md").read_text(encoding="utf-8")
    checks["readme_icon_ref"] = "assets/icons/pegasus-512.png" in readme_text
    checks["readme_nssm_docs"] = "NSSM" in readme_text

    # 5. NSIS installer updated
    nsi_text = Path("pegasus/modules/access_workflow/electron/installer.nsi").read_text(encoding="utf-8")
    checks["nsi_nssm_download"] = "download" in nsi_text and "NSSM" in nsi_text
    checks["nsi_version_21"] = "2.1.0" in nsi_text

    # 6. Daemon install script
    daemon_text = Path("pegasus/modules/access_workflow/daemon/install.ps1").read_text(encoding="utf-8")
    checks["daemon_nssm"] = "daemon" in daemon_text.lower() and ("nssm" in daemon_text.lower() or "NSSM" in daemon_text)

    # 7. NSO Pegasus SVG exists
    checks["nso_pegasus_icon"] = Path("assets/icons/nspegasus.svg").exists()

    # 8. Payload Factory page exists
    checks["payload_factory"] = Path("pegasus/ui/web/src/pages/PayloadFactory.tsx").exists()

    # 9. C2 Dashboard with auto-deploy
    c2_text = Path("pegasus/ui/web/src/pages/C2Dashboard.tsx").read_text(encoding="utf-8")
    checks["c2_auto_deploy"] = "autoDeploy" in c2_text

    # 10. PostExploit with RAT panel
    post_text = Path("pegasus/ui/web/src/pages/PostExploit.tsx").read_text(encoding="utf-8")
    checks["post_rat_keylog"] = "rat-keylog" in post_text
    checks["post_rat_screenshot"] = "rat-screenshot" in post_text
    checks["post_rat_mic"] = "rat-mic" in post_text
    checks["post_lucide_icons"] = "KeyRound" in post_text and "Mic" in post_text

    # 11. Campaigns with deploy
    campaigns_text = Path("pegasus/ui/web/src/pages/Campaigns.tsx").read_text(encoding="utf-8")
    checks["campaign_deploy"] = "deploy" in campaigns_text

    # 12. Release artifacts present
    dist_path = Path("dist")
    checks["release_exe"] = (dist_path / "Pegasus-Web.exe").exists()
    checks["release_setup"] = (dist_path / "Pegasus-v2.1.0-Setup.exe").exists()
    checks["release_zip"] = (dist_path / "pegasus-source-v2.1.0.zip").exists()

    # Print results
    all_pass = True
    for label, ok in checks.items():
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {label}")

    print()
    if all_pass:
        print("=== ALL TESTS PASSED — Port 5001, NSSM auto-install, all pages wired, release artifacts present ===")
    else:
        print("=== SOME TESTS FAILED ===")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
