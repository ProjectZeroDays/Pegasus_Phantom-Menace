"""
Pegasus ML engine - defensive telemetry anomaly analytics.

Pure stdlib implementation:
- Incremental EWMA mean/variance (West 1979) -> z-score anomaly gating
- Sequence (n-gram) behavior predictor for event streams
- Dry-run automated-response planner (never executes destructive actions)
- JSONL feedback store that nudges gates based on operator verdicts
  ("continuous learning"; honestly labeled - no online gradient descent)
"""
from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path.home() / ".pegasus"
FEEDBACK_PATH = DATA_DIR / "feedback.jsonl"


class EWMAStat:
    """Incremental mean/variance with exponential decay on history."""

    def __init__(self, decay: float = 0.08) -> None:
        self.decay = decay
        self.n = 0
        self.mean = 0.0
        self.var = 1.0

    def update(self, value: float) -> float:
        self.n += 1
        if self.n == 1:
            self.mean = float(value)
            self.var = 1.0
            return 0.0
        delta = float(value) - self.mean
        incr = self.decay * delta
        prev_mean = self.mean
        self.mean += incr
        self.var = (1.0 - self.decay) * (self.var + delta * (float(value) - prev_mean) * self.decay)
        if self.var < 1e-9:
            self.var = 1e-9
        return delta / math.sqrt(self.var)

    def zscore(self, value: float) -> float:
        if self.n < 2:
            return 0.0
        return (float(value) - self.mean) / math.sqrt(self.var)


class AnomalyGate:
    """Per-metric anomaly gating with a tunable threshold."""

    def __init__(self, threshold: float = 3.0, decay: float = 0.08) -> None:
        self.threshold = threshold
        self.stats: Dict[str, EWMAStat] = defaultdict(lambda: EWMAStat(decay))

    def observe(self, metric: str, value: float) -> Dict[str, Any]:
        st = self.stats[metric]
        z_pre = st.zscore(value)
        st.update(value)
        is_anomaly = abs(z_pre) >= self.threshold and st.n >= 10
        return {
            "metric": metric,
            "value": float(value),
            "z": round(z_pre, 3),
            "threshold": self.threshold,
            "n": st.n,
            "mean": round(st.mean, 4),
            "is_anomaly": is_anomaly,
        }


class BehaviorPredictor:
    """N-gram (order-2 by default) transition predictor over event tokens."""

    def __init__(self, order: int = 2) -> None:
        self.order = max(1, order)
        self.model: Dict[Tuple[str, ...], Counter] = defaultdict(Counter)
        self.counts: Counter = Counter()

    def train(self, events: List[str]) -> int:
        if not events:
            return 0
        padded = (["<START>"] * self.order) + list(events)
        added = 0
        for i in range(len(padded) - self.order):
            ctx = tuple(padded[i : i + self.order])
            nxt = padded[i + self.order]
            self.model[ctx][nxt] += 1
            added += 1
        self.counts[" ".join(events)] += added
        return added

    def predict(self, context: List[str]) -> Dict[str, Any]:
        ctx = tuple((["<START>"] * self.order + list(context))[-self.order :])
        nxt = self.model.get(ctx)
        if not nxt:
            return {"context": list(context), "prediction": None, "probability": 0.0, "trained": False}
        total = sum(nxt.values())
        token, count = nxt.most_common(1)[0]
        return {
            "context": list(context),
            "prediction": token,
            "probability": round(count / total, 4),
            "alternatives": [{"token": t, "p": round(c / total, 4)} for t, c in nxt.most_common(5)],
            "trained": True,
        }


class FeedbackStore:
    """Operator verdict log used to nudge gate thresholds (continuous learning)."""

    def __init__(self, path: Path = FEEDBACK_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, metric: str, verdict: str, notes: str = "") -> Dict[str, Any]:
        verdict = verdict.lower()
        if verdict not in {"true_positive", "false_positive", "true_negative", "false_negative"}:
            raise ValueError("verdict must be one of true_positive|false_positive|true_negative|false_negative")
        entry = {"ts": time.time(), "metric": metric, "verdict": verdict, "notes": notes}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return entry

    def stats(self) -> Dict[str, Any]:
        tally = Counter()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    tally[json.loads(line).get("verdict", "unknown")] += 1
                except json.JSONDecodeError:
                    continue
        return dict(tally)

    def suggested_threshold(self, current: float = 3.0) -> Dict[str, Any]:
        s = self.stats()
        tp, fp = s.get("true_positive", 0), s.get("false_positive", 0)
        if tp + fp < 5:
            return {"current": current, "suggested": current, "reason": "insufficient feedback (<5 verdicts)"}
        fp_rate = fp / (tp + fp)
        if fp_rate > 0.5:
            suggested = min(5.0, current + 0.5)
        elif fp_rate < 0.1:
            suggested = max(2.0, current - 0.5)
        else:
            suggested = current
        return {"current": current, "suggested": suggested, "fp_rate": round(fp_rate, 3)}


class ResponsePlanner:
    """Dry-run automated response. Advisory only; nothing executes blindly."""

    _PLAYBOOK = {
        "low": ["log", "tag_log", "monitor"],
        "medium": ["log", "tag_log", "raise_alert", "enrich_context"],
        "high": ["log", "tag_log", "raise_alert", "session_advisory_throttle", "notify_oncall"],
        "critical": ["log", "raise_alert", "notify_oncall", "advisory_quarantine_offer", "capture_forensic_snapshot"],
    }

    def plan(self, severity: str, context: str = "") -> Dict[str, Any]:
        severity = severity.lower()
        actions = self._PLAYBOOK.get(severity, self._PLAYBOOK["medium"])
        return {
            "severity": severity,
            "context": context,
            "dry_run": True,
            "actions": actions,
            "requires_operator_confirm": any("advisory" in a for a in actions),
            "never_executed": True,
        }
