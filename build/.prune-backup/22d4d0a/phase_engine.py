"""Phase engine: typed gates."""
class PhaseGate:
    def __init__(self, phase: str, entry_predicate: dict, exit_proof: dict):
        self.phase = phase
        self.entry = entry_predicate
        self.exit = exit_proof
    def can_enter(self, state: dict):
        return all(state.get(k) == v for k,v in self.entry.items())
    def can_exit(self, state: dict):
        return all(state.get(k) == v for k,v in self.exit.items())

PHASES = [
    PhaseGate("recon", {"device.serial":"*","auth.token":"*"}, {"payload.url":"*"}),
    PhaseGate("access", {"payload.url":"*"}, {"session_id":"*"}),
    PhaseGate("persist", {"session_id":"*"}, {"success_code":"200"}),
    PhaseGate("elevate", {"success_code":"200"}, {"lateral_target":"*"}),
    PhaseGate("exfil", {"lateral_target":"*"}, {"exfil_complete":True}),
]
if __name__ == '__main__':
    for g in PHASES:
        print(f"Phase {g.phase}: entry={g.entry} exit={g.exit}")
