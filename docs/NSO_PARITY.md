# NSO-class capability parity

This page maps the publicly documented behaviour of NSO Group's Pegasus Android
implant family onto concrete, importable implementations in this repository.
Parity is measured by the resolver in `pegasus/modules/access_workflow/nso_capabilities.py`
and exposed at `GET /api/nso/capabilities` and `GET /api/capabilities`.

## Coverage model

| Level | Meaning |
| --- | --- |
| `native` | Implemented end to end against the live device or artefact |
| `shell` | Implemented through Android shell primitives; works within the stated device/permission limits |
| `partial` | Real, but depends on an on-device component or optional tooling |
| `external` | Delegates to an installed external stack (Frida, Metasploit, Nmap) |

Only `native`, `shell` and `partial` rows count as implementation. `external`
rows resolve to a module that is shipped, and the external tool is detected at
run time.

## Capability map

| Capability | Category | Level | Implementation |
| --- | --- | --- | --- |
| Zero-click delivery | delivery | native | `zero_click.run_exploit` |
| Network / SMS delivery | delivery | shell | `nso_ops.device_serial` + wireless ADB |
| Steganographic delivery | delivery | native | `steganography.embed` |
| QR delivery | delivery | partial | `nso_ops.push_and_launch` + QR generator |
| Device fingerprint | targeting | native | `nso_ops.device_profile` |
| Mass payload generation | targeting | native | `mass_payload.generate_batch` |
| Target list management | targeting | native | `campaign_manager` |
| SMS collection | collection | shell | `nso_ops.collect_sms` |
| Call log collection | collection | shell | `nso_ops.collect_call_log` |
| Contact harvesting | collection | shell | `nso_ops.collect_contacts` |
| Calendar extraction | collection | shell | `nso_ops.collect_calendar` |
| App inventory | collection | native | `nso_ops.app_inventory` |
| Messaging app data | collection | partial | `nso_ops.pull_app_data` (run-as) |
| Artefact exfiltration | collection | native | `post_exploitation.run("exfiltrate")` |
| Location tracking | surveillance | shell | `nso_ops.last_location` |
| Screen capture | surveillance | native | `nso_ops.screen_capture` |
| Camera capture | surveillance | partial | `nso_ops.camera_capture` |
| Live microphone | surveillance | partial | `nso_ops.mic_note` / RAT module |
| Keystroke capture | surveillance | shell | `nso_ops.keylog` |
| Implant install | control | native | `nso_ops.push_and_launch` |
| Persistence | control | native | `post_exploitation.run("persistence")` |
| Self-destruct | control | native | `nso_ops.uninstall` / `wipe_app` |
| App suppression | control | native | `nso_ops.disable_package` |
| Remote command control | control | native | `telegram_control.start_bot` |
| FRP unlock | control | native | `frp_unlock.run` |
| AV mutation engine | evasion | native | `ai_mutation.analyse` |
| SSL pinning bypass | evasion | external | `mitm_framework` + Frida script writer |
| C2 server | infrastructure | native | `c2_server` |
| Anonymity layer | infrastructure | native | `anonymity` |
| Reporting | infrastructure | native | `export` |

## Known constraints

* Shell collection of SMS, contacts, calls and calendar requires the `content`
  provider to be readable without root. Heavily locked OEM builds can deny it.
* `pull_app_data` only reaches app sandboxes on debuggable builds (`run-as`).
* Live microphone needs an on-device recorder; `mic_note` documents the route
  and the RAT module provides the implant side.
* Location reads the last fix from `dumpsys location`; it is not a continuous
  tracker. Use the device telemetry sampler for history.
* Camera capture drives the system camera UI, so a locked screen needs the
  camera intent to be permitted.

## Verification

```
pegasus capabilities --assert-parity
```

The command exits non-zero when a target fails to import or parity is below
100%. Both web surfaces render the same report, so a regression is visible in
the UI as a red `missing` row.
