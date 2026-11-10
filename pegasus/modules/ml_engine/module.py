"""ML engine module (Phase 22) - anomaly detection, behavior prediction, response planning."""
from __future__ import annotations

import json

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import HookType

from pegasus.modules.ml_engine.analyzer import (
    AnomalyGate, BehaviorPredictor, FeedbackStore, ResponsePlanner,
)


class MLEngineModule(BaseModule):
    """Defensive ML analytics for Pegasus telemetry."""

    def __init__(self, context) -> None:
        super().__init__(context)
        self._gate = AnomalyGate(threshold=3.0)
        self._predictor = BehaviorPredictor(order=2)
        self._feedback = FeedbackStore()
        self._planner = ResponsePlanner()

    @property
    def module_name(self) -> str:
        return "ML Engine"

    @property
    def module_description(self) -> str:
        return "Anomaly detection, behavior prediction, automated response, continuous learning"

    @property
    def module_category(self) -> str:
        return "intelligence"

    async def _register_commands(self) -> None:
        self.register_command("ml-anomaly-check", "Score a metric sample (EWMA z-score)", self.cmd_anomaly_check)
        self.register_command("ml-behavior-predict", "Predict next event from a token sequence", self.cmd_behavior_predict)
        self.register_command("ml-response-plan", "Dry-run response plan for a severity tier", self.cmd_response_plan)
        self.register_command("ml-feedback", "Record operator verdict (true_positive|false_positive|...)", self.cmd_feedback)
        self.register_command("ml-feedback-stats", "Show verdict tally and suggested gate threshold", self.cmd_feedback_stats)
        self.register_command("ml-learn-events", "Train the n-gram predictor on a token sequence", self.cmd_learn_events)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="ml_engine_dashboard",
            component_type="panel",
            path="/ml",
            title="ML Engine Dashboard",
            icon="brain",
            order=12,
        )

    async def _register_hooks(self) -> None:
        pass

    async def cmd_anomaly_check(self, *args) -> None:
        if len(args) >= 2:
            metric, raw = args[0], args[1]
        else:
            metric = self.prompt("Metric name", default="api_latency_ms") or "api_latency_ms"
            raw = self.prompt("Sample value", default="0") or "0"
        try:
            value = float(raw)
        except (TypeError, ValueError):
            self.print_error("value must be numeric")
            return
        result = self._gate.observe(str(metric), value)
        if result["is_anomaly"]:
            self.print_warning(f"ANOMALY {json.dumps(result)}")
        else:
            self.print_success(json.dumps(result))

    async def cmd_behavior_predict(self, *args) -> None:
        raw = " ".join(str(a) for a in args) or (self.prompt("Event tokens (space separated)", default="login fail fail") or "")
        tokens = [t for t in raw.split() if t]
        print(json.dumps(self._predictor.predict(tokens), indent=2))

    async def cmd_response_plan(self, *args) -> None:
        severity = (str(args[0]) if args else (self.prompt("Severity (low|medium|high|critical)", default="high") or "high")).lower()
        context = " ".join(str(a) for a in args[1:]) if len(args) > 1 else ""
        print(json.dumps(self._planner.plan(severity, context), indent=2))

    async def cmd_feedback(self, *args) -> None:
        if len(args) >= 2:
            metric, verdict = args[0], args[1]
            notes = " ".join(str(a) for a in args[2:])
        else:
            metric = self.prompt("Metric", default="api_latency_ms") or "api_latency_ms"
            verdict = self.prompt("Verdict (true_positive|false_positive|true_negative|false_negative)", default="false_positive") or "false_positive"
            notes = self.prompt("Notes", default="") or ""
        try:
            entry = self._feedback.record(str(metric), str(verdict), str(notes))
        except ValueError as exc:
            self.print_error(str(exc))
            return
        self.print_success(f"verdict recorded: {entry['verdict']} for {entry['metric']}")

    async def cmd_feedback_stats(self, *args) -> None:
        print(json.dumps({
            "verdicts": self._feedback.stats(),
            "gate": self._feedback.suggested_threshold(self._gate.threshold),
        }, indent=2))

    async def cmd_learn_events(self, *args) -> None:
        raw = " ".join(str(a) for a in args) or (self.prompt("Event tokens to train (space separated)", default="login access deny grant") or "")
        tokens = [t for t in raw.split() if t]
        n = self._predictor.train(tokens)
        self.print_success(f"trained on {len(tokens)} tokens, {n} transitions")
