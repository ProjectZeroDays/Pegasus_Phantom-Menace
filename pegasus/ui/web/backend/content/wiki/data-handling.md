# Data handling

Collected data is evidence. Treat it that way.

## Storage

Operator state lives in `~/.pegasus`. The vault keeps sealed artefacts under
`~/.pegasus/vault`, encrypted with AES-256-GCM where the `cryptography`
package is available.

## Exfiltration

Transfer only what the engagement permits. Use the relay or tunnel surfaces
so transfers are logged.

## Retention

Delete collection artefacts when the engagement closes and the client asks.
The console never deletes evidence on its own.
