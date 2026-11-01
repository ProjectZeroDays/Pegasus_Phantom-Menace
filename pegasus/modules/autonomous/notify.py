"""Desktop notification plus optional webhook."""
import os
import platform
import shutil
import subprocess

import requests


def notify(title: str, body: str) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            safe = body.replace('"', "'")
            ps = ('[Windows.UI.Notifications.ToastNotificationManager,'
                  ' Windows.UI.Notifications, ContentType=WindowsRuntime] > $null; '
                  '$t=[Windows.UI.Notifications.ToastNotificationManager]'
                  '.GetTemplateContent(2); '
                  f'$t.GetElementsByTagName("text")[0].AppendChild('
                  f'$t.CreateTextNode("{title}"))|Out-Null; '
                  f'$t.GetElementsByTagName("text")[1].AppendChild('
                  f'$t.CreateTextNode("{safe}"))|Out-Null; '
                  '[Windows.UI.Notifications.ToastNotificationManager]'
                  '.CreateToastNotifier("Pegasus").Show($t)')
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=15)
        elif system == "Darwin":
            subprocess.run(["osascript", "-e",
                            f'display notification "{body}" with title "{title}"'],
                           timeout=10)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", title, body], timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass
    hook = os.environ.get("PEGASUS_NOTIFY_WEBHOOK")
    if hook:
        try:
            requests.post(hook, json={"title": title, "body": body}, timeout=10)
        except requests.RequestException:
            pass
