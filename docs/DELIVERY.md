# Delivery channels

Payload URLs are handed to the target through real Android intents. Each
channel targets the production package and MIME type, and every send is logged
to `~/.pegasus/delivery_history.jsonl`.

## Channels

| Key | Surface | Intent |
| --- | --- | --- |
| `sms` | SMS | `SENDTO sms:<number>` with `sms_body` |
| `whatsapp` | WhatsApp | `SEND text/plain -p com.whatsapp` |
| `whatsapp_audio` | WhatsApp voice note | spoken URL as `audio/*` |
| `telegram` | Telegram | `SEND text/plain -p org.telegram.messenger` |
| `signal` | Signal | `SEND text/plain -p org.thoughtcrime.securesms` |
| `messenger` | Messenger | `SEND text/plain -p com.facebook.orca` |
| `messenger_audio` | Messenger voice note | spoken URL as `audio/*` |
| `discord` | Discord | `SEND text/plain -p com.discord` |
| `viber`, `slack`, `teams`, `google_messages` | other chat apps | `SEND text/plain` |
| `email` | Email | `SENDTO mailto:<address>` with subject |
| `bluetooth` | Bluetooth share | `SEND` targeting `com.android.bluetooth` |
| `nfc` | NFC handler | share to `com.android.nfc` |
| `dialer` | Phone app | `DIAL tel:<number>` |
| `any` | Share sheet | unbound `SEND` |

## Payload server

`POST /api/delivery/serve` starts a threaded HTTP server on `0.0.0.0:<port>` and
returns the LAN URL (`http://<ip>:<port>/`). `POST /api/delivery/stage` copies a
file into the served directory; `POST /api/catalog/build` with `stage: true`
builds a carrier and stages it in one step.

## Audio

Audio channels synthesise a spoken transcript with Windows SAPI
(`System.Speech`), push the WAV to `/sdcard/Download/` and attach it with
`EXTRA_STREAM` and a read grant. If SAPI is unavailable a silent WAV is written
so the intent still succeeds. The transcript replaces punctuation with words
("dot", "slash", "port") so text-to-speech reads the URL correctly.

## Constraints

* The composer opens populated; `auto_send` presses Enter after 1.6 s. Apps
  that show a recipient picker still need a tap.
* Bluetooth and NFC need the receiver in range and a paired/host device.
* Audio attachments depend on the app accepting `audio/*` from a `file://`
  stream, which Messenger and WhatsApp do.
