# Merged Workflows — Q-ANDROID v17.7 INFEROR + Pegasus Phantom Menace
# /all /finish /swarm /never-ask /improve

WORKFLOWS = {
  "frp-unlock": {"qandroid": "9_complete.py / FrpRecovery (usb/qr/talkback/emergency/root/auto)", "pegasus": "pegasus/modules/access_workflow/module.py cmd_access_autonomous"},
  "payload-gen": {"qandroid": "build_wasm / build_mp4 / payload-qr", "pegasus": "pegasus/modules/payload/module.py cmd_payload_gen / cmd_payload_bind / cmd_payload_mass"},
  "payload-mutate": {"qandroid": "embedded inferor stage / AI mutation", "pegasus": "cmd_payload_mutate (apktool stub + AV sig scan)"},
  "payload-dna": {"qandroid": "crypto/Kyber/Dilithium registry", "pegasus": "cmd_payload_dna (get_dna_dir -> registry.json)"},
  "fingerprint": {"qandroid": "AdbLocator / TcpTransport / Preflight", "pegasus": "fingerprint command (10.1.10.89:5555)"},
  "harvest": {"qandroid": "ContentHarvester SMS/calls/contacts/calendar/media", "pegasus": "collect device content pipeline"},
  "access-autonomous": {"qandroid": "FRP + USB -> TCPIP + pairing + mDNS + QR", "pegasus": "autonomous access workflow (ADB/Fastboot/QR/USB)"},
  "sessions": {"qandroid": "AdbModule devices / props / reverse / screenshot", "pegasus": "sessions / metasploit RPC (port 55553)"},
  "crypto_selftest": {"qandroid": "KyberKEM + DilithiumSignature", "pegasus": "imported from qandroid_inferor_complete.py"},
  "menu": {"qandroid": "PEGASUS v1.3 blue/green 3-col menu", "pegasus": "UI dashboard + command registry"},
}

# Integration: 9_complete.py copied to pegasus/qandroid_inferor_complete.py
# All controls (security, connectivity, content, payload, AI, config) now shared.
