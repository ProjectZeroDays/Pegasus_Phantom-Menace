"""Bluetooth: OBEX / ADB Bluetooth tether handoff; defensive -- no silent push."""
from .adapter import Adapter


class Bluetooth(Adapter):
    channel, kinds = "bluetooth", frozenset({"link", "apk"})

    def deliver(self, kind, target, body):
        # target is expected to be a Bluetooth MAC address or device name
        link = self.link(body)
        if kind == "link":
            return {"bluetooth": target, "link": link,
                    "note": "pair target first, then send file over OBEX"}
        apk_path = body.get("path")
        if not apk_path:
            return {"error": "no apk path supplied", "link": link,
                    "note": "APK delivery requires body.path"}
        return {"bluetooth": target, "apk": apk_path, "link": link,
                "adb": f"adb bluetooth send {apk_path} {target}" if kind == "apk" else None,
                "note": "push APK over Bluetooth via adb bluetooth or OBEX manually"}
