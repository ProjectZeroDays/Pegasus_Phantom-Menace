# Zero-Click Exploit Suite

Five device families, thirteen vectors, one registry.

| Family | Transport | Vector | Key |
| --- | --- | --- | --- |
| Android (generic) | binder | Binder UAF / OOB write chain | `android_binder` |
| Android (generic) | media | MediaCodec parser corruption | `android_mediacodec` |
| Android (generic) | bluetooth | HFP/HID keystroke injection | `android_bluetooth` |
| OnePlus | oem-service | OxygenOS service surface | `oneplus_oxygenos` |
| OnePlus | baseband | Qualcomm modem frame probe | `oneplus_qualcomm_modem` |
| Pixel 8 | baseband | Tensor G3 modem SIB probe | `pixel8_modem` |
| Pixel 8 | wifi | Broadcom management frame probe | `pixel8_wifi` |
| Pixel 8 | usb | Titan M2 accessory descriptor probe | `pixel8_titan_m2_usb` |
| Pixel 8 | nfc | NDEF parser payload | `pixel8_nfc` |
| Samsung S24 | baseband | Exynos 2400 modem probe | `samsung_exynos_modem` |
| Samsung S24 | knox | Knox policy bypass chain | `samsung_knox_bypass` |
| Xiaomi | oem-service | MIUI service surface | `xiaomi_miui_service` |
| Xiaomi | oem-service | HyperOS service surface | `xiaomi_hyperos` |

## CLI

```
pegasus zeroclick-list [--family pixel8] [--transport nfc]
pegasus zeroclick-run android_bluetooth
```

## Python

```python
from pegasus.modules.access_workflow.zero_click import list_exploits, run_exploit

run_exploit("pixel8_modem", target="192.168.1.100")
```

Every vector returns a dictionary containing `status`, the parsed observations
and a `commands` list describing the ADB or radio steps it exercised, so
results can be replayed or attached to a report.

All exploits are for authorized security research and penetration testing only.
