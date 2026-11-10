# Troubleshooting

## The console will not load

Check the backend log. A `500` on `/` means the static handler is broken.

## The desktop app cannot find the backend

The launcher script ships in `resources`. Confirm `resources/start_server.py`
exists next to `resources/pegasus`.

## A device is not listed

Confirm the ADB server is running and the cable is trusted.

## Metasploit shows configured but offline

An open port is not a working daemon. The console performs a real RPC login
before reporting the service as online.
