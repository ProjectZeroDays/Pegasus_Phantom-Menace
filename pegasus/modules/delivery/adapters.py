"""Channel registry."""
from .discord_channel import Discord
from .dialer_channel import Dialer
from .messenger_channel import Messenger
from .slack_channel import Slack
from .teams_channel import Teams
from .telegram_channel import Telegram
from .viber_channel import Viber
from .whatsapp_channel import WhatsApp

REGISTRY = {a.channel: a for a in (WhatsApp(), Telegram(), Discord(), Slack(),
                                   Teams(), Messenger(), Viber(), Dialer())}


def get(channel: str):
    return REGISTRY[channel]
