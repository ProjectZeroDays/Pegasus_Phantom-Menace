"""
Pegasus Phantom Menace v2 - Workflow Monitoring & Analytics

Robust monitoring and logging system for debugging and tuning
autonomous exploitation workflows. Provides feedback loops for
self-healing, self-learning optimization of exploit effectiveness.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class WorkflowMonitor:
    """
    Robust monitoring and logging for autonomous workflows.
    
    Tracks:
    - Per-vector success rates
    - Stage-by-stage timing and outcomes
    - Adaptive decision patterns
    - Self-healing events
    - Exploit effectiveness trends
    """

    def __init__(self, console: Console, log_dir: Optional[Path] = None):
        self.console = console
        self.log_dir = log_dir or Path("logs/access_workflow")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.log_dir / "workflow_metrics.db"
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for structured metrics."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                category TEXT,
                target TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_ms INTEGER,
                overall_success INTEGER,
                vectors_tested INTEGER,
                exploits_attempted INTEGER,
                self_healing_attempts INTEGER,
                adaptive_decisions INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS stage_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                stage TEXT,
                success INTEGER,
                vectors_tested INTEGER,
                exploit_attempts INTEGER,
                access_established INTEGER,
                notes TEXT,
                timestamp TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS exploit_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                exploit_id TEXT,
                vector TEXT,
                target TEXT,
                cve_id TEXT,
                exploit_name TEXT,
                result TEXT,
                duration_ms INTEGER,
                timestamp TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                stage TEXT,
                decision TEXT,
                reasoning TEXT,
                output_based INTEGER,
                timestamp TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
        """)
        conn.commit()
        conn.close()

    def log_run(self, run_data: Dict[str, Any]):
        """Log a complete workflow run."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data.get("run_id"),
            run_data.get("category"),
            run_data.get("target"),
            run_data.get("start_time"),
            run_data.get("end_time"),
            run_data.get("total_duration_ms"),
            1 if run_data.get("overall_success") else 0,
            run_data.get("vectors_tested", 0),
            run_data.get("exploits_attempted", 0),
            run_data.get("self_healing_attempts", 0),
            run_data.get("adaptive_decisions", 0),
        ))
        conn.commit()
        conn.close()

    def log_stage(self, run_id: str, stage_data: Dict[str, Any]):
        """Log a stage result."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT INTO stage_results VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            stage_data.get("stage"),
            1 if stage_data.get("success") else 0,
            stage_data.get("vectors_tested", 0),
            stage_data.get("exploit_attempts", 0),
            1 if stage_data.get("access_established") else 0,
            stage_data.get("notes", ""),
            stage_data.get("timestamp"),
        ))
        conn.commit()
        conn.close()

    def log_exploit(self, run_id: str, exploit_data: Dict[str, Any]):
        """Log a single exploit attempt."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT INTO exploit_attempts VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            exploit_data.get("exploit_id"),
            exploit_data.get("vector"),
            exploit_data.get("target"),
            exploit_data.get("cve_id"),
            exploit_data.get("exploit_name"),
            exploit_data.get("result"),
            exploit_data.get("duration_ms", 0),
            exploit_data.get("timestamp"),
        ))
        conn.commit()
        conn.close()

    def log_decision(self, run_id: str, decision_data: Dict[str, Any]):
        """Log an adaptive decision."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT INTO adaptive_decisions VALUES (NULL, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            decision_data.get("stage"),
            decision_data.get("decision"),
            decision_data.get("reasoning"),
            1 if decision_data.get("output_based") else 0,
            decision_data.get("timestamp"),
        ))
        conn.commit()
        conn.close()

    def get_success_rate_by_vector(self) -> Dict[str, float]:
        """Calculate success rate per vector from exploit attempts."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            SELECT vector,
                   SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END) as successes,
                   COUNT(*) as total
            FROM exploit_attempts
            GROUP BY vector
        """)
        rows = c.fetchall()
        conn.close()
        return {row[0]: (row[1] / row[2] * 100 if row[2] else 0) for row in rows}

    def get_stage_success_rates(self) -> Dict[str, float]:
        """Calculate success rate per stage."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            SELECT stage,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                   COUNT(*) as total
            FROM stage_results
            GROUP BY stage
        """)
        rows = c.fetchall()
        conn.close()
        return {row[0]: (row[1] / row[2] * 100 if row[2] else 0) for row in rows}

    def get_recent_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent run history."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            SELECT * FROM runs ORDER BY start_time DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()
        columns = ["run_id", "category", "target", "start_time", "end_time",
                   "duration_ms", "overall_success", "vectors_tested",
                   "exploits_attempted", "self_healing_attempts",
                   "adaptive_decisions"]
        return [dict(zip(columns, row)) for row in rows]

    def get_optimization_recommendations(self) -> List[str]:
        """Generate intelligent recommendations for workflow optimization."""
        recommendations = []
        rates = self.get_success_rate_by_vector()
        stage_rates = self.get_stage_success_rates()

        # Vector recommendations
        if rates:
            best = max(rates.items(), key=lambda x: x[1])
            worst = min(rates.items(), key=lambda x: x[1])
            recommendations.append(
                f"Prioritize {best[0]} vector (success rate: {best[1]:.1f}%)"
            )
            if worst[1] < 20:
                recommendations.append(
                    f"Review or deprioritize {worst[0]} vector (success rate: {worst[1]:.1f}%)"
                )

        # Stage recommendations
        if stage_rates:
            failed_stages = [s for s, r in stage_rates.items() if r < 50]
            if failed_stages:
                recommendations.append(
                    f"Focus improvement on stages: {', '.join(failed_stages)}"
                )

        return recommendations

    def display_dashboard(self):
        """Display the monitoring dashboard."""
        rates = self.get_success_rate_by_vector()
        stage_rates = self.get_stage_success_rates()
        runs = self.get_recent_runs(10)
        recommendations = self.get_optimization_recommendations()

        self.console.print("\n[bold cyan]Workflow Monitoring Dashboard[/bold cyan]\n")

        # Success rates table
        table = Table(title="Exploit Success Rates by Vector", header_style="bold cyan")
        table.add_column("Vector", style="bold yellow")
        table.add_column("Success Rate (%)", style="white")
        for vector, rate in sorted(rates.items(), key=lambda x: -x[1]):
            table.add_row(vector, f"{rate:.1f}%")
        self.console.print(table)

        # Stage success rates
        table2 = Table(title="Stage Success Rates", header_style="bold cyan")
        table2.add_column("Stage", style="bold yellow")
        table2.add_column("Success Rate (%)", style="white")
        for stage, rate in sorted(stage_rates.items(), key=lambda x: -x[1]):
            table2.add_row(stage, f"{rate:.1f}%")
        self.console.print(table2)

        # Recent runs
        if runs:
            table3 = Table(title="Recent Runs", header_style="bold cyan")
            table3.add_column("Run ID", style="bold yellow")
            table3.add_column("Target", style="white")
            table3.add_column("Category", style="cyan")
            table3.add_column("Success", style="green")
            table3.add_column("Duration (s)", style="white")
            for run in runs:
                table3.add_row(
                    run["run_id"],
                    run["target"],
                    run["category"],
                    "Yes" if run["overall_success"] else "No",
                    f"{run['duration_ms'] / 1000:.1f}",
                )
            self.console.print(table3)

        # Recommendations
        if recommendations:
            self.console.print("\n[bold yellow]Optimization Recommendations:[/bold yellow]")
            for rec in recommendations:
                self.console.print(f"  • {rec}")

        self.console.print()


class PerformanceAnalytics:
    """Analytics engine for self-learning workflow optimization."""

    def __init__(self, monitor: WorkflowMonitor):
        self.monitor = monitor

    def analyze_patterns(self) -> Dict[str, Any]:
        """Analyze exploit patterns to identify effective combinations."""
        rates = self.monitor.get_success_rate_by_vector()
        stage_rates = self.monitor.get_stage_success_rates()
        return {
            "vector_success_rates": rates,
            "stage_success_rates": stage_rates,
            "best_vector": max(rates.items(), key=lambda x: x[1])[0] if rates else None,
            "worst_vector": min(rates.items(), key=lambda x: x[1])[0] if rates else None,
            "total_runs": len(self.monitor.get_recent_runs(100)),
        }

    def suggest_adaptive_parameters(self, current_stage: str,
                                     previous_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Suggest adaptive parameters based on previous outputs."""
        suggestions = {
            "retry_count": 1,
            "timeout_multiplier": 1.0,
            "preferred_vectors": [],
            "avoid_vectors": [],
        }

        rates = self.monitor.get_success_rate_by_vector()
        for vector, rate in rates.items():
            if rate > 50:
                suggestions["preferred_vectors"].append(vector)
            elif rate < 10:
                suggestions["avoid_vectors"].append(vector)

        # Adjust based on previous output patterns
        if previous_outputs:
            last_output = previous_outputs[-1]
            if last_output.get("result") == "blocked":
                suggestions["timeout_multiplier"] = 2.0
                suggestions["retry_count"] = 3

        return suggestions


# Module entry point
metadata = None  # Set by plugin loader


def create_monitor(console: Console) -> WorkflowMonitor:
    return WorkflowMonitor(console)


def create_analytics(monitor: WorkflowMonitor) -> PerformanceAnalytics:
    return PerformanceAnalytics(monitor)
