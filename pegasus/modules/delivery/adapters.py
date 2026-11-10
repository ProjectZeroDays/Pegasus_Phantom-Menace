"""Channel registry."""
from .bluetooth_channel import Bluetooth
from .discord_channel import Discord
from .dialer_channel import Dialer
from .dispatch_channel import Dispatch
from .email_channel import Email
from .links_channel import Links
from .media_channel import Media
from .messenger_channel import Messenger
from .nfc_channel import NFC
from .signal_channel import Signal
from .sms_channel import SMS
from .slack_channel import Slack
from .teams_channel import Teams
from .telegram_channel import Telegram
from .viber_channel import Viber
from .whatsapp_channel import WhatsApp

REGISTRY = {a.channel: a for a in (
    WhatsApp(), Telegram(), Discord(), Slack(), Teams(), Messenger(),
    Viber(), Dialer(), SMS(), Signal(), Email(), Bluetooth(), NFC(),
    Media(), Links(), Dispatch())}


def get(channel: str):
    return REGISTRY[channel]
