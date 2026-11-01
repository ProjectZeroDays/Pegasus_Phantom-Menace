"""Viber deep link."""
import re

from .adapter import Adapter


class Viber(Adapter):
    channel, kinds = "viber", frozenset({"link"})

    def deliver(self, kind, target, body):
        return {"link": f"viber://chat?number=%2B{re.sub(r'[^0-9]', '', target)}"}
