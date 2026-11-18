# Security posture

## Bind addresses

| Variable | Default | Meaning |
|---|---|---|
| `PEGASUS_HOST` | `127.0.0.1` | Console bind. Loopback: the console is a local single-operator tool. Set `0.0.0.0` to publish it. |
| `PEGASUS_C2_HOST` | `127.0.0.1` | C2 listener bind. Follows the console posture; `POST /api/c2/start` accepts a `host` validated against loopback, the wildcards and the host's own interface addresses. |
| `PEGASUS_C2_TLS` | `0` | `0` plain HTTP, `1`/`adhoc` self-signed, anything else an explicit `certfile` or `certfile:keyfile`. |

`POST /api/c2/start` refuses a host that is neither `127.0.0.1`, `0.0.0.0`,
`::1`, `::` nor a local interface address, so a typo cannot produce a listener
nobody can reach.

## Operator gate

`PEGASUS_REQUIRE_AUTH` is **opt-in**. Unset (default) the console runs
unauthenticated as a local tool and `operator.current()` returns the local
identity. Set it and every route needs a token or session, and the CSRF check
applies to writes. Publishing the console on `0.0.0.0` without setting this flag
publishes it unauthenticated.

## Token rotation

The live `ghp_` PAT is redundant: tooling authenticates through the Windows
credential manager (`gh auth setup-git`, `credential.helper=manager`) with a
keyring `gho_` token. Revoke the PAT at GitHub → Settings → Developer settings →
Personal access tokens. No literal remains in any tracked file, but it was
exposed for the length of the engagement.

## extract-zip

Two Dependabot alerts, no upstream fix, ignored in `.github/dependabot.yml`.

- **Where:** build-time only, a transitive dependency of `electron-builder`'s
  unpack path. Not shipped inside the installer, so not reachable at runtime.
- **Exposure:** a malicious archive processed during `npm run dist:win`.
- **Mitigation:** build from tagged trees only, and pre-inspect any third-party
  `.zip` before it reaches the build. Revisit when upstream patches.

## Vendored tree

`weapons/` carries 396 of the 497 advisories including all 16 criticals. It is
226 tracked files of third-party `strix-agent 0.8.3`, not a submodule, so each
one needs a vendoring decision. There is no Dependabot entry for it by design.

## Known gaps

- The C2 kill command lands on the implant's next signed beacon. It does not
  reach out to the device.
- BB84 QKD is a classical-RNG simulation. Lamport OTS is single-message.
- The token ledger is local JSON accounting, not a chain.
