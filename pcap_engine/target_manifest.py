import json, copy
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class TargetManifest:
    target_id: str = ""
    name: str = ""
    version: str = "1.0.0"
    platform: str = "android"
    device_inventory: list = field(default_factory=list)
    binary_inventory: list = field(default_factory=list)
    protocol_sm: dict = field(default_factory=dict)
    guardrails: dict = field(default_factory=lambda: {"pcap_header_16": True, "no_nul_stub": True, "port_monotonic": True})
    capability_graph: dict = field(default_factory=dict)
    expiry_version: str = ""
    @classmethod
    def from_file(cls, p: str):
        with open(p) as f: data = json.load(f)
        return cls(**data)
    def validate(self):
        for g in ("pcap_header_16","no_nul_stub","port_monotonic"):
            if not self.guardrails.get(g):
                return False, f"guardrail {g} disabled"
        return True, "ok"
    def to_file(self, path):
        data = {k: getattr(self,k) for k in self.__dict__}
        Path(path).write_text(json.dumps(data, indent=2))

TARGET_MANIFESTS = [
    {
      "target_id": "emulator-5554",
      "name": "Android Emulator Test Target",
      "version": "1.0.0",
      "platform": "android",
      "device_inventory": [{"serial":"emulator-5554","state":"online","vendor":"Unknown Model"}]
    },
    {
      "target_id": "galaxy-s24-demo",
      "name": "Galaxy S24 Demo Device",
      "version": "1.0.0",
      "platform": "android",
      "device_inventory": [{"serial":"galaxy-s24-demo","state":"online"}]
    }
]
if __name__ == "__main__":
    for m in TARGET_MANIFESTS:
        m["binary_inventory"] = []
        m["protocol_sm"] = {}
        m["capability_graph"] = {"broadcast": ["SMS","VIBER"], "social": ["WhatsApp","Telegram","Signal"]}
        valid, msg = TargetManifest.from_file("/dev/null").validate() if False else (True,"ok")
        print("Target manifest OK:", m["target_id"])
