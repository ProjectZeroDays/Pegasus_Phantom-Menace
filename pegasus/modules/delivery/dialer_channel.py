"""MMI/USSD handoff. Returns the adb line an operator would run."""
from urllib.parse import quote

from .adapter import Adapter


class Dialer(Adapter):
    channel, kinds = "dialer", frozenset({"link"})

    def deliver(self, kind, target, body):
        code = body.get("mmi") or "*#*#4636#*#*"
        return {"mmi": code, "link": self.link(body),
                "adb": f"adb shell am start -a android.intent.action.DIAL "
                       f"-d 'tel:{quote(code)}'"}
