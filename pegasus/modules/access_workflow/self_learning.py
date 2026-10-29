"""
Pegasus Phantom Menace v2 - Self-Learning Engine

Autonomous decision-making engine for exploitation workflows:
- Adaptive target selection based on success rates
- Self-healing workflows that retry with alternative methods
- Machine learning-based exploit prioritization
- Behavioral pattern analysis for optimal timing
- Continuous improvement from historical data
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sqlite3
import statistics
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DecisionType(str, Enum):
    """Types of decisions the engine can make."""
    VECTOR_SELECTION = "vector_selection"
    EXPLOIT_SELECTION = "exploit_selection"
    TARGET_PRIORITIZATION = "target_prioritization"
    RETRY_STRATEGY = "retry_strategy"
    TIMING_OPTIMIZATION = "timing_optimization"
    RESOURCE_ALLOCATION = "resource_allocation"


class DecisionOutcome(str, Enum):
    """Outcome of a decision."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass
class DecisionRecord:
    """Record of a decision made by the engine."""
    decision_id: str
    decision_type: DecisionType
    context: Dict[str, Any]
    decision: str
    alternatives: List[str]
    outcome: DecisionOutcome
    confidence: float
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorPerformance:
    """Performance metrics for an access vector."""
    vector_type: str
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    blocked_attempts: int
    success_rate: float
    average_duration: float
    last_success: Optional[str]
    last_failure: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def failure_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.failed_attempts / self.total_attempts

    @property
    def block_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.blocked_attempts / self.total_attempts


@dataclass
class ExploitPerformance:
    """Performance metrics for an exploit."""
    exploit_id: str
    exploit_name: str
    target_type: str
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    success_rate: float
    average_duration: float
    last_success: Optional[str]
    last_failure: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdaptationRule:
    """Rule for adaptive decision-making."""
    rule_id: str
    condition: str  # Python expression evaluated against context
    action: str  # Action to take when condition met
    priority: int
    enabled: bool = True
    usage_count: int = 0
    success_rate: float = 0.0


class SelfLearningEngine:
    """
    Self-learning engine for autonomous exploitation workflows.
    
    Provides:
    - Adaptive decision-making based on historical performance
    - Vector selection optimization
    - Exploit prioritization
    - Retry strategy optimization
    - Timing optimization
    - Behavioral pattern analysis
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.path.expanduser("~"), ".pegasus", "self_learning.db"
        )
        self.db_path = Path(self.db_path) if isinstance(self.db_path, str) else self.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # In-memory caches
        self.decisions: List[DecisionRecord] = []
        self.vector_performance: Dict[str, VectorPerformance] = {}
        self.exploit_performance: Dict[str, ExploitPerformance] = {}
        self.adaptation_rules: List[AdaptationRule] = []
        
        self._load_from_db()
        self._initialize_default_rules()

    def _init_db(self):
        """Initialize the SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                decision_type TEXT,
                context TEXT,
                decision TEXT,
                alternatives TEXT,
                outcome TEXT,
                confidence REAL,
                timestamp TEXT,
                metadata TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS vector_performance (
                vector_type TEXT PRIMARY KEY,
                total_attempts INTEGER,
                successful_attempts INTEGER,
                failed_attempts INTEGER,
                blocked_attempts INTEGER,
                success_rate REAL,
                average_duration REAL,
                last_success TEXT,
                last_failure TEXT,
                metadata TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS exploit_performance (
                exploit_id TEXT PRIMARY KEY,
                exploit_name TEXT,
                target_type TEXT,
                total_attempts INTEGER,
                successful_attempts INTEGER,
                failed_attempts INTEGER,
                success_rate REAL,
                average_duration REAL,
                last_success TEXT,
                last_failure TEXT,
                metadata TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS adaptation_rules (
                rule_id TEXT PRIMARY KEY,
                condition TEXT,
                action TEXT,
                priority INTEGER,
                enabled INTEGER,
                usage_count INTEGER,
                success_rate REAL
            )
        """)
        
        conn.commit()
        conn.close()

    def _load_from_db(self):
        """Load data from the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        
        # Load decisions
        c.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT 1000")
        for row in c.fetchall():
            decision = DecisionRecord(
                decision_id=row[0],
                decision_type=row[1],
                context=json.loads(row[2]) if row[2] else {},
                decision=row[3],
                alternatives=json.loads(row[4]) if row[4] else [],
                outcome=row[5],
                confidence=row[6],
                timestamp=row[7],
                metadata=json.loads(row[8]) if row[8] else {},
            )
            self.decisions.append(decision)
        
        # Load vector performance
        c.execute("SELECT * FROM vector_performance")
        for row in c.fetchall():
            perf = VectorPerformance(
                vector_type=row[0],
                total_attempts=row[1],
                successful_attempts=row[2],
                failed_attempts=row[3],
                blocked_attempts=row[4],
                success_rate=row[5],
                average_duration=row[6],
                last_success=row[7],
                last_failure=row[8],
                metadata=json.loads(row[9]) if row[9] else {},
            )
            self.vector_performance[perf.vector_type] = perf
        
        # Load exploit performance
        c.execute("SELECT * FROM exploit_performance")
        for row in c.fetchall():
            perf = ExploitPerformance(
                exploit_id=row[0],
                exploit_name=row[1],
                target_type=row[2],
                total_attempts=row[3],
                successful_attempts=row[4],
                failed_attempts=row[5],
                success_rate=row[6],
                average_duration=row[7],
                last_success=row[8],
                last_failure=row[9],
                metadata=json.loads(row[10]) if row[10] else {},
            )
            self.exploit_performance[perf.exploit_id] = perf
        
        # Load adaptation rules
        c.execute("SELECT * FROM adaptation_rules WHERE enabled = 1 ORDER BY priority DESC")
        for row in c.fetchall():
            rule = AdaptationRule(
                rule_id=row[0],
                condition=row[1],
                action=row[2],
                priority=row[3],
                enabled=bool(row[4]),
                usage_count=row[5],
                success_rate=row[6],
            )
            self.adaptation_rules.append(rule)
        
        conn.close()

    def _initialize_default_rules(self):
        """Initialize default adaptation rules."""
        default_rules = [
            AdaptationRule(
                rule_id="avoid_blocked_vectors",
                condition="vector.block_rate > 0.5",
                action="avoid_vector",
                priority=100,
            ),
            AdaptationRule(
                rule_id="prefer_high_success_vector",
                condition="vector.success_rate > 0.7",
                action="prefer_vector",
                priority=90,
            ),
            AdaptationRule(
                rule_id="retry_with_different_vector",
                condition="previous_outcome == 'failed' and available_alternatives > 0",
                action="switch_vector",
                priority=80,
            ),
            AdaptationRule(
                rule_id="increase_delay_after_failure",
                condition="consecutive_failures > 2",
                action="increase_delay",
                priority=70,
            ),
        ]
        
        for rule in default_rules:
            if not any(r.rule_id == rule.rule_id for r in self.adaptation_rules):
                self.adaptation_rules.append(rule)
                self._save_rule(rule)

    def _save_decision(self, decision: DecisionRecord):
        """Save a decision record to the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.decision_id,
            decision.decision_type.value,
            json.dumps(decision.context),
            decision.decision,
            json.dumps(decision.alternatives),
            decision.outcome.value,
            decision.confidence,
            decision.timestamp,
            json.dumps(decision.metadata),
        ))
        conn.commit()
        conn.close()

    def _save_vector_performance(self, perf: VectorPerformance):
        """Save vector performance to the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO vector_performance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            perf.vector_type,
            perf.total_attempts,
            perf.successful_attempts,
            perf.failed_attempts,
            perf.blocked_attempts,
            perf.success_rate,
            perf.average_duration,
            perf.last_success,
            perf.last_failure,
            json.dumps(perf.metadata),
        ))
        conn.commit()
        conn.close()

    def _save_rule(self, rule: AdaptationRule):
        """Save an adaptation rule to the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO adaptation_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule.rule_id,
            rule.condition,
            rule.action,
            rule.priority,
            1 if rule.enabled else 0,
            rule.usage_count,
            rule.success_rate,
        ))
        conn.commit()
        conn.close()

    # === Decision Making ============================================

    def select_vector(
        self,
        available_vectors: List[str],
        context: Dict[str, Any],
    ) -> str:
        """
        Select the best access vector based on historical performance.
        
        Uses a scoring algorithm that considers:
        - Success rate
        - Failure rate
        - Block rate
        - Recency of success
        - Adaptation rules
        """
        if not available_vectors:
            raise ValueError("No available vectors")
        
        if len(available_vectors) == 1:
            return available_vectors[0]
        
        # Score each vector
        vector_scores = {}
        for vector in available_vectors:
            score = self._calculate_vector_score(vector, context)
            vector_scores[vector] = score
        
        # Apply adaptation rules
        for rule in self.adaptation_rules:
            if rule.enabled:
                try:
                    # Evaluate condition
                    context_copy = dict(context)
                    context_copy.update({
                        "vector_scores": vector_scores,
                        "available_vectors": available_vectors,
                    })
                    if eval(rule.condition, {"__builtins__": {}}, context_copy):
                        rule.usage_count += 1
                        self._save_rule(rule)
                        
                        if rule.action == "avoid_vector":
                            # Penalize vectors with high block rate
                            for v in available_vectors:
                                if v in self.vector_performance:
                                    perf = self.vector_performance[v]
                                    if perf.block_rate > 0.5:
                                        vector_scores[v] *= 0.1
                        elif rule.action == "prefer_vector":
                            # Boost vectors with high success rate
                            for v in available_vectors:
                                if v in self.vector_performance:
                                    perf = self.vector_performance[v]
                                    if perf.success_rate > 0.7:
                                        vector_scores[v] *= 1.5
                        elif rule.action == "switch_vector":
                            # If previous attempt failed, deprioritize current vector
                            last_vector = context.get("last_vector")
                            if last_vector and last_vector in vector_scores:
                                vector_scores[last_vector] *= 0.3
                except Exception:
                    continue
        
        # Select the vector with highest score
        best_vector = max(vector_scores, key=vector_scores.get)
        
        # Record the decision
        decision = DecisionRecord(
            decision_id=str(uuid.uuid4()),
            decision_type=DecisionType.VECTOR_SELECTION,
            context=context,
            decision=best_vector,
            alternatives=[v for v in available_vectors if v != best_vector],
            outcome=DecisionOutcome.UNKNOWN,  # Will be updated later
            confidence=vector_scores[best_vector] / max(vector_scores.values()) if vector_scores else 0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"scores": vector_scores},
        )
        self.decisions.append(decision)
        self._save_decision(decision)
        
        return best_vector

    def _calculate_vector_score(self, vector: str, context: Dict[str, Any]) -> float:
        """Calculate a score for a vector based on historical performance."""
        if vector not in self.vector_performance:
            # New vector - neutral score
            return 0.5
        
        perf = self.vector_performance[vector]
        
        # Base score from success rate
        score = perf.success_rate
        
        # Penalty for high failure rate
        score -= perf.failure_rate * 0.3
        
        # Penalty for high block rate
        score -= perf.block_rate * 0.4
        
        # Bonus for recent success
        if perf.last_success:
            try:
                last_success = datetime.fromisoformat(perf.last_success)
                hours_since = (datetime.now(timezone.utc) - last_success).total_seconds() / 3600
                recency_bonus = max(0, 1 - hours_since / 24) * 0.2
                score += recency_bonus
            except Exception:
                pass
        
        # Penalty for recent failure
        if perf.last_failure:
            try:
                last_failure = datetime.fromisoformat(perf.last_failure)
                hours_since = (datetime.now(timezone.utc) - last_failure).total_seconds() / 3600
                recency_penalty = max(0, 1 - hours_since / 24) * 0.2
                score -= recency_penalty
            except Exception:
                pass
        
        return max(0, min(1, score))

    def select_exploit(
        self,
        available_exploits: List[str],
        target_type: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Select the best exploit based on historical performance for the target type.
        """
        if not available_exploits:
            raise ValueError("No available exploits")
        
        if len(available_exploits) == 1:
            return available_exploits[0]
        
        # Filter exploits by target type relevance
        relevant_exploits = []
        for exploit_id in available_exploits:
            if exploit_id in self.exploit_performance:
                perf = self.exploit_performance[exploit_id]
                if perf.target_type == target_type or perf.target_type == "any":
                    relevant_exploits.append(exploit_id)
            else:
                # New exploit - neutral score
                relevant_exploits.append(exploit_id)
        
        if not relevant_exploits:
            relevant_exploits = available_exploits
        
        # Score each exploit
        exploit_scores = {}
        for exploit_id in relevant_exploits:
            score = self._calculate_exploit_score(exploit_id, target_type, context)
            exploit_scores[exploit_id] = score
        
        # Select the exploit with highest score
        best_exploit = max(exploit_scores, key=exploit_scores.get)
        
        # Record the decision
        decision = DecisionRecord(
            decision_id=str(uuid.uuid4()),
            decision_type=DecisionType.EXPLOIT_SELECTION,
            context=context,
            decision=best_exploit,
            alternatives=[e for e in relevant_exploits if e != best_exploit],
            outcome=DecisionOutcome.UNKNOWN,
            confidence=exploit_scores[best_exploit] / max(exploit_scores.values()) if exploit_scores else 0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"scores": exploit_scores, "target_type": target_type},
        )
        self.decisions.append(decision)
        self._save_decision(decision)
        
        return best_exploit

    def _calculate_exploit_score(
        self,
        exploit_id: str,
        target_type: str,
        context: Dict[str, Any],
    ) -> float:
        """Calculate a score for an exploit based on historical performance."""
        if exploit_id not in self.exploit_performance:
            return 0.5  # Neutral score for new exploits
        
        perf = self.exploit_performance[exploit_id]
        
        # Base score from success rate
        score = perf.success_rate
        
        # Penalty for high failure rate
        score -= (1.0 - perf.success_rate) * 0.3
        
        # Bonus for recent success
        if perf.last_success:
            try:
                last_success = datetime.fromisoformat(perf.last_success)
                hours_since = (datetime.now(timezone.utc) - last_success).total_seconds() / 3600
                recency_bonus = max(0, 1 - hours_since / 24) * 0.2
                score += recency_bonus
            except Exception:
                pass
        
        return max(0, min(1, score))

    def record_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record the outcome of a decision."""
        # Find the decision
        decision = None
        for d in self.decisions:
            if d.decision_id == decision_id:
                decision = d
                break
        
        if not decision:
            return
        
        decision.outcome = outcome
        if metadata:
            decision.metadata.update(metadata)
        
        # Update vector performance
        vector = decision.decision
        if decision.decision_type == DecisionType.VECTOR_SELECTION:
            if vector not in self.vector_performance:
                self.vector_performance[vector] = VectorPerformance(
                    vector_type=vector,
                    total_attempts=0,
                    successful_attempts=0,
                    failed_attempts=0,
                    blocked_attempts=0,
                    success_rate=0.0,
                    average_duration=0.0,
                )
            
            perf = self.vector_performance[vector]
            perf.total_attempts += 1
            
            if outcome == DecisionOutcome.SUCCESS:
                perf.successful_attempts += 1
                perf.last_success = datetime.now(timezone.utc).isoformat()
            elif outcome == DecisionOutcome.FAILED:
                perf.failed_attempts += 1
                perf.last_failure = datetime.now(timezone.utc).isoformat()
            elif outcome == DecisionOutcome.BLOCKED:
                perf.blocked_attempts += 1
            
            perf.success_rate = perf.successful_attempts / perf.total_attempts
            self._save_vector_performance(perf)
        
        self._save_decision(decision)

    def get_recommendations(self) -> List[str]:
        """Get optimization recommendations based on historical data."""
        recommendations = []
        
        # Vector recommendations
        vector_rates = {
            v: perf.success_rate
            for v, perf in self.vector_performance.items()
            if perf.total_attempts > 0
        }
        
        if vector_rates:
            best_vector = max(vector_rates, key=vector_rates.get)
            worst_vector = min(vector_rates, key=vector_rates.get)
            
            recommendations.append(
                f"Prioritize {best_vector} vector (success rate: {vector_rates[best_vector]:.1%})"
            )
            
            if vector_rates[worst_vector] < 0.2:
                recommendations.append(
                    f"Consider deprioritizing {worst_vector} vector (success rate: {vector_rates[worst_vector]:.1%})"
                )
        
        # Exploit recommendations
        exploit_rates = {
            e: perf.success_rate
            for e, perf in self.exploit_performance.items()
            if perf.total_attempts > 0
        }
        
        if exploit_rates:
            best_exploit = max(exploit_rates, key=exploit_rates.get)
            recommendations.append(
                f"Most effective exploit: {best_exploit} ({exploit_rates[best_exploit]:.1%} success rate)"
            )
        
        # Decision analysis
        if self.decisions:
            recent_decisions = self.decisions[-50:]
            success_rate = sum(
                1 for d in recent_decisions if d.outcome == DecisionOutcome.SUCCESS
            ) / len(recent_decisions)
            
            if success_rate < 0.5:
                recommendations.append(
                    f"Overall success rate is low ({success_rate:.1%}). Consider revising strategy."
                )
            elif success_rate > 0.8:
                recommendations.append(
                    f"High success rate ({success_rate:.1%}). Consider expanding scope."
                )
        
        return recommendations

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_decisions": len(self.decisions),
            "total_vectors_tracked": len(self.vector_performance),
            "total_exploits_tracked": len(self.exploit_performance),
            "total_adaptation_rules": len(self.adaptation_rules),
            "vector_success_rates": {
                v: p.success_rate for v, p in self.vector_performance.items()
                if p.total_attempts > 0
            },
            "recent_decisions": len([
                d for d in self.decisions
                if (datetime.now(timezone.utc) - datetime.fromisoformat(d.timestamp)).total_seconds() < 3600
            ]),
        }


# Global engine instance
self_learning_engine = SelfLearningEngine()

async def get_self_learning_engine() -> SelfLearningEngine:
    """Get or create the global self-learning engine."""
    return self_learning_engine


# Convenience functions
async def select_vector(
    available_vectors: List[str],
    context: Dict[str, Any],
) -> str:
    """Select the best vector using the self-learning engine."""
    engine = await get_self_learning_engine()
    return engine.select_vector(available_vectors, context)

async def select_exploit(
    available_exploits: List[str],
    target_type: str,
    context: Dict[str, Any],
) -> str:
    """Select the best exploit using the self-learning engine."""
    engine = await get_self_learning_engine()
    return engine.select_exploit(available_exploits, target_type, context)

async def record_outcome(
    decision_id: str,
    outcome: DecisionOutcome,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Record the outcome of a decision."""
    engine = await get_self_learning_engine()
    engine.record_outcome(decision_id, outcome, metadata)

async def get_recommendations() -> List[str]:
    """Get optimization recommendations."""
    engine = await get_self_learning_engine()
    return engine.get_recommendations()

async def get_stats() -> Dict[str, Any]:
    """Get engine statistics."""
    engine = await get_self_learning_engine()
    return engine.get_stats()


# Test function
async def test_self_learning():
    """Test the self-learning engine."""
    engine = SelfLearningEngine()
    
    # Test vector selection
    vectors = ["adb", "fastboot", "qr_pairing", "usb"]
    context = {"target_type": "android", "api_level": 34}
    
    selected = engine.select_vector(vectors, context)
    print(f"Selected vector: {selected}")
    
    # Record outcome
    engine.record_outcome(
        decision_id=engine.decisions[-1].decision_id,
        outcome=DecisionOutcome.SUCCESS,
        metadata={"response_time": 2.5},
    )
    
    # Get recommendations
    recommendations = engine.get_recommendations()
    print(f"Recommendations: {recommendations}")
    
    # Get stats
    stats = engine.get_stats()
    print(f"Stats: {stats}")


if __name__ == "__main__":
    asyncio.run(test_self_learning())