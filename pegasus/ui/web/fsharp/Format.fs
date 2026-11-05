module Pegasus.Fsharp.Format

/// Compact duration from seconds. Mirrors formatDuration in lib/format.ts.
let duration (seconds: int) : string =
    if seconds < 60 then sprintf "%ds" seconds
    elif seconds < 3600 then sprintf "%dm %ds" (seconds / 60) (seconds % 60)
    else sprintf "%dh %dm" (seconds / 3600) (seconds % 3600 / 60)
