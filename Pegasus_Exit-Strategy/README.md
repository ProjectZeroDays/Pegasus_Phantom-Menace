# Pegasus Exit Strategy

A focused fork of **Pegasus Phantom Menace** for engagement close-out.

Pegasus is an authorised security-testing platform. Exit Strategy is the same
platform pointed at the last mile of an engagement: teardown, evidence
hand-over, credential rotation and the written close-out report.

It reuses the original Pegasus identity - the same logo, the same colour
tokens - so an operator moving between the two applications is not
re-learning anything.

## What it covers

| Surface | Purpose |
|---|---|
| Teardown checklist | Every task that must happen before an engagement closes |
| Evidence inventory | What was collected, where it lives, and who holds the copy |
| Access revocation | The accounts, keys and tunnels opened during the work |
| Close-out report | The written summary handed to the client |

## Running it

```
python Pegasus_Exit-Strategy/app.py --port 5098
```

The console opens on `http://127.0.0.1:5098/`.

## Relationship to Pegasus

Exit Strategy shares the Pegasus plugin system, the agent layer and the
operator store, so a checklist written in Pegasus can be carried straight
into the close-out run. It deliberately ships none of the active
capabilities - it only records and verifies teardown.

## Authorisation

Authorised security testing only. Exit Strategy exists to make engagements
end *cleanly*.
