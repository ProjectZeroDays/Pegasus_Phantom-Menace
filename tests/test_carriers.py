import pytest

from pegasus.modules.delivery import carriers


@pytest.mark.parametrize("channel,requested,network,expected", [
    ("sms", "pdf", None, "link"),
    ("mms", "pdf", None, "link"),
    ("email", "pdf", None, "pdf"),
    ("messenger", "pdf", None, "pdf_lure"),
    ("email", "pdf", "att", "link"),
    ("whatsapp", "apk", None, "apk"),
])
def test_routing_guard(channel, requested, network, expected):
    assert carriers.carrier_for(channel, requested, network) == expected


def test_unknown_channel_raises():
    with pytest.raises(KeyError):
        carriers.dispatch("carrierpigeon", "link", "+15550001", {})
