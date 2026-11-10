"""
Social Engineering Server for Enhanced Phishing Campaigns
Enterprise-grade social engineering platform for phishing simulations and security training
Implements sophisticated phishing campaigns, credential harvesting, and deception frameworks
"""

from typing import *
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing_extensions import TypedDict
import asyncio
import json
import logging
import random
import hashlib
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing_extensions import Literal

logger = logging.getLogger(__name__)

class PhishingCampaign(BaseModel):
    """Phishing campaign configuration"""
    campaign_id: str
    name: str
    target_audience: str
    attack_vector: Literal["email", "sms", "social_media", "phone", "in_person"]
    subject_template: str
    body_template: str
    landing_url: str
    success_criteria: Dict[str, Any]
    duration: int  # hours
    targets: List[Dict[str, Any]]
    metadata: Dict[str, Any] = {}
    status: Literal["draft", "active", "paused", "completed", "cancelled"] = "draft"
    created_at: datetime
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

class DeceptionFramework(BaseModel):
    """Deception framework configuration"""
    framework_id: str
    name: str
    description: str
    scenario_type: Literal["scenario_based", "identity_based", "relationship_based"]
    target_profile: Dict[str, Any]
    deception_tactics: List[Dict[str, Any]]
    detection_techniques: List[Dict[str, Any]]
    effectiveness_score: float = 0.0
    risk_level: str = "low"
    metadata: Dict[str, Any] = {}

class PhishingAttempt(BaseModel):
    """Phishing attempt tracking"""
    attempt_id: str
    campaign_id: str
    target: Dict[str, Any]
    attack_vector: str
    status: Literal["sent", "opened", "clicked", "credential_submitted", "blocked", "failed"]
    timestamp: datetime
    ip_address: str
    user_agent: str
    source_url: Optional[str] = None
    credentials_attempted: bool = False
    outcome: str = "unknown"
    detection_result: Optional[str] = None

class SecurityTrainingModule(BaseModel):
    """Security training module"""
    module_id: str
    title: str
    description: str
    content: str
    interactive: bool = False
    difficulty: str = "medium"
    estimated_time: int  # minutes
    prerequisites: List[str] = []
    learning_objectives: List[str] = []
    completion_tracking: bool = True

class SocialEngineeringServer:
    """Social Engineering Server Implementation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.phishing_campaigns: Dict[str, PhishingCampaign] = {}
        self.deception_frameworks: Dict[str, DeceptionFramework] = {}
        self.phishing_attempts: List[PhishingAttempt] = []
        self.security_training_modules: List[SecurityTrainingModule] = []
        self.target_database: Dict[str, Any] = {}
        self.attacker_profile: Dict[str, Any] = {}
        self.is_running = False
        self.server = None
        self.campaign_scheduler = None
        self.attempt_tracker = None

    async def start(self) -> None:
        """Start social engineering server"""
        logger.info("Starting social engineering server")

        try:
            # Initialize campaign scheduler
            self.campaign_scheduler = asyncio.create_task(self._campaign_scheduler_loop())

            # Initialize attempt tracker
            self.attempt_tracker = asyncio.create_task(self._attempt_tracker_loop())

            # Create FastAPI application
            self.app = FastAPI(
                title="Social Engineering Server",
                description="Enterprise social engineering and phishing simulation platform",
                version="1.0.0"
            )

            # Setup routes
            self._setup_routes()

            # Start server
            import uvicorn

            config = uvicorn.Config(
                app=self.app,
                host="0.0.0.0",
                port=8001,
                log_level="info"
            )

            self.server = uvicorn.Server(config)
            self.is_running = True

            logger.info("Social engineering server started successfully")
            await self.server.serve()

        except Exception as e:
            logger.error(f"Failed to start social engineering server: {e}")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """Stop social engineering server"""
        if self.server:
            self.server.shutdown()
            self.is_running = False

        if self.campaign_scheduler:
            self.campaign_scheduler.cancel()
        if self.attempt_tracker:
            self.attempt_tracker.cancel()

        logger.info("Social engineering server stopped")

    def _setup_routes(self) -> None:
        """Setup API routes"""

        @self.app.get("/health")
        async def health_check(request: Request) -> Dict[str, str]:
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "active_campaigns": len([c for c in self.phishing_campaigns.values() if c.status == "active"])
            }

        @self.app.post("/campaigns")
        async def create_campaign(request: Request, campaign_data: Dict[str, Any]) -> Dict[str, str]:
            campaign_id = f"campaign_{datetime.now().timestamp()}"
            campaign = PhishingCampaign(
                campaign_id=campaign_id,
                name=campaign_data.get("name", "New Campaign"),
                target_audience=campaign_data.get("target_audience", "general"),
                attack_vector=campaign_data.get("attack_vector", "email"),
                subject_template=campaign_data.get("subject_template", ""),
                body_template=campaign_data.get("body_template", ""),
                landing_url=campaign_data.get("landing_url", ""),
                success_criteria=campaign_data.get("success_criteria", {}),
                duration=campaign_data.get("duration", 24),
                targets=campaign_data.get("targets", []),
                metadata=campaign_data.get("metadata", {}),
                status=campaign_data.get("status", "draft"),
                created_at=datetime.now(),
                scheduled_start=campaign_data.get("scheduled_start"),
                scheduled_end=campaign_data.get("scheduled_end")
            )

            self.phishing_campaigns[campaign_id] = campaign

            logger.info(f"Created phishing campaign {campaign_id}: {campaign.name}")

            return {
                "campaign_id": campaign_id,
                "status": "created",
                "message": f"Phishing campaign created: {campaign.name}"
            }

        @self.app.get("/campaigns")
        async def list_campaigns(request: Request) -> Dict[str, Any]:
            return {
                "campaigns": list(self.phishing_campaigns.values()),
                "count": len(self.phishing_campaigns)
            }

        @self.app.get("/campaigns/{campaign_id}")
        async def get_campaign(self, request: Request, campaign_id: str) -> Dict[str, Any]:
            if campaign_id not in self.phishing_campaigns:
                return {"error": "Campaign not found"}, 404

            campaign = self.phishing_campaigns[campaign_id]
            return {
                "campaign_id": campaign.campaign_id,
                "name": campaign.name,
                "target_audience": campaign.target_audience,
                "attack_vector": campaign.attack_vector,
                "subject_template": campaign.subject_template,
                "body_template": campaign.body_template,
                "landing_url": campaign.landing_url,
                "success_criteria": campaign.success_criteria,
                "duration": campaign.duration,
                "targets": campaign.targets,
                "metadata": campaign.metadata,
                "status": campaign.status,
                "created_at": campaign.created_at.isoformat(),
                "scheduled_start": campaign.scheduled_start.isoformat() if campaign.scheduled_start else None,
                "scheduled_end": campaign.scheduled_end.isoformat() if campaign.scheduled_end else None
            }

        @self.app.put("/campaigns/{campaign_id}")
        async def update_campaign(self, request: Request, campaign_id: str, campaign_data: Dict[str, Any]) -> Dict[str, str]:
            if campaign_id not in self.phishing_campaigns:
                return {"error": "Campaign not found"}, 404

            campaign = self.phishing_campaigns[campaign_id]
            if "name" in campaign_data:
                campaign.name = campaign_data["name"]
            if "target_audience" in campaign_data:
                campaign.target_audience = campaign_data["target_audience"]
            if "attack_vector" in campaign_data:
                campaign.attack_vector = campaign_data["attack_vector"]
            if "subject_template" in campaign_data:
                campaign.subject_template = campaign_data["subject_template"]
            if "body_template" in campaign_data:
                campaign.body_template = campaign_data["body_template"]
            if "landing_url" in campaign_data:
                campaign.landing_url = campaign_data["landing_url"]
            if "success_criteria" in campaign_data:
                campaign.success_criteria = campaign_data["success_criteria"]
            if "duration" in campaign_data:
                campaign.duration = campaign_data["duration"]
            if "targets" in campaign_data:
                campaign.targets = campaign_data["targets"]
            if "metadata" in campaign_data:
                campaign.metadata.update(campaign_data["metadata"])
            if "status" in campaign_data:
                campaign.status = campaign_data["status"]

            campaign.created_at = datetime.now()

            logger.info(f"Updated campaign {campaign_id}")
            return {
                "message": f"Campaign {campaign_id} updated",
                "status": "updated"
            }

        @self.app.post("/campaigns/{campaign_id}/start")
        async def start_campaign(self, request: Request, campaign_id: str) -> Dict[str, str]:
            if campaign_id not in self.phishing_campaigns:
                return {"error": "Campaign not found"}, 404

            campaign = self.phishing_campaigns[campaign_id]
            campaign.status = "active"

            logger.info(f"Started campaign {campaign_id}: {campaign.name}")

            return {
                "message": f"Campaign {campaign_id} started",
                "status": "started",
                "campaign_id": campaign_id
            }

        @self.app.post("/campaigns/{campaign_id}/stop")
        async def stop_campaign(self, request: Request, campaign_id: str) -> Dict[str, str]:
            if campaign_id not in self.phishing_campaigns:
                return {"error": "Campaign not found"}, 404

            campaign = self.phishing_campaigns[campaign_id]
            campaign.status = "paused"

            logger.info(f"Stopped campaign {campaign_id}")

            return {
                "message": f"Campaign {campaign_id} stopped",
                "status": "stopped"
            }

        @self.app.delete("/campaigns/{campaign_id}")
        async def delete_campaign(self, request: Request, campaign_id: str) -> Dict[str, str]:
            if campaign_id not in self.phishing_campaigns:
                return {"error": "Campaign not found"}, 404

            del self.phishing_campaigns[campaign_id]
            logger.info(f"Deleted campaign {campaign_id}")
            return {
                "message": f"Campaign {campaign_id} deleted",
                "status": "deleted"
            }

        @self.app.post("/attempts")
        async def create_attempt(request: Request, attempt_data: Dict[str, Any]) -> Dict[str, str]:
            attempt_id = f"attempt_{datetime.now().timestamp()}"
            attempt = PhishingAttempt(
                attempt_id=attempt_id,
                campaign_id=attempt_data["campaign_id"],
                target=attempt_data["target"],
                attack_vector=attempt_data["attack_vector"],
                status=attempt_data.get("status", "sent"),
                timestamp=datetime.now(),
                ip_address=attempt_data.get("ip_address", ""),
                user_agent=attempt_data.get("user_agent", ""),
                source_url=attempt_data.get("source_url"),
                credentials_attempted=attempt_data.get("credentials_attempted", False),
                outcome=attempt_data.get("outcome", "unknown"),
                detection_result=attempt_data.get("detection_result")
            )

            self.phishing_attempts.append(attempt)
            logger.info(f"Created phishing attempt {attempt_id} for campaign {attempt_data['campaign_id']}")

            return {
                "attempt_id": attempt_id,
                "status": "created",
                "message": f"Phishing attempt created for campaign {attempt_data['campaign_id']}"
            }

        @self.app.get("/attempts")
        async def list_attempts(request: Request) -> Dict[str, Any]:
            return {
                "attempts": [attempt.dict() for attempt in self.phishing_attempts],
                "count": len(self.phishing_attempts)
            }

        @self.app.get("/attempts/{attempt_id}")
        async def get_attempt(self, request: Request, attempt_id: str) -> Dict[str, Any]:
            attempt = next((a for a in self.phishing_attempts if a.attempt_id == attempt_id), None)
            if not attempt:
                return {"error": "Attempt not found"}, 404

            return attempt.dict()

        @self.app.post("/attempts/{attempt_id}/update")
        async def update_attempt(self, request: Request, attempt_id: str, update_data: Dict[str, Any]) -> Dict[str, str]:
            attempt = next((a for a in self.phishing_attempts if a.attempt_id == attempt_id), None)
            if not attempt:
                return {"error": "Attempt not found"}, 404

            if "status" in update_data:
                attempt.status = update_data["status"]
            if "credentials_attempted" in update_data:
                attempt.credentials_attempted = update_data["credentials_attempted"]
            if "outcome" in update_data:
                attempt.outcome = update_data["outcome"]
            if "detection_result" in update_data:
                attempt.detection_result = update_data["detection_result"]

            logger.info(f"Updated attempt {attempt_id}: {attempt.status}")
            return {
                "message": f"Attempt {attempt_id} updated",
                "status": "updated"
            }

        @self.app.post("/generate-deception")
        async def generate_deception(request: Request, deception_data: Dict[str, Any]) -> Dict[str, Any]:
            deception_id = f"deception_{datetime.now().timestamp()}"
            deception = DeceptionFramework(
                framework_id=deception_id,
                name=deception_data.get("name", "New Deception Framework"),
                description=deception_data.get("description", ""),
                scenario_type=deception_data.get("scenario_type", "scenario_based"),
                target_profile=deception_data.get("target_profile", {}),
                deception_tactics=deception_data.get("deception_tactics", []),
                detection_techniques=deception_data.get("detection_techniques", []),
                effectiveness_score=deception_data.get("effectiveness_score", 0.0),
                risk_level=deception_data.get("risk_level", "low"),
                metadata=deception_data.get("metadata", {})
            )

            self.deception_frameworks[deception_id] = deception

            logger.info(f"Generated deception framework {deception_id}: {deception.name}")

            return {
                "deception_id": deception_id,
                "status": "created",
                "message": f"Deception framework created: {deception.name}"
            }

        @self.app.get("/deception")
        async def list_deception(request: Request) -> Dict[str, Any]:
            return {
                "deception_frameworks": list(self.deception_frameworks.values()),
                "count": len(self.deception_frameworks)
            }

        @self.app.post("/generate-link")
        async def generate_landing_page(request: Request, generation_data: Dict[str, Any]) -> Dict[str, str]:
            landing_url = f"https://landing.example.com/{generation_data.get('campaign_id', '')}/{datetime.now().timestamp()}"
            logger.info(f"Generated landing page {landing_url} for campaign {generation_data.get('campaign_id', '')}")
            return {
                "landing_url": landing_url,
                "status": "created",
                "message": f"Landing page generated: {landing_url}"
            }

        @self.app.post("/process-credential-harvest")
        async def process_credential_harvest(request: Request, harvest_data: Dict[str, Any]) -> Dict[str, str]:
            # Record credential harvest attempt
            attempt_id = f"harvest_{datetime.now().timestamp()}"
            attempt = PhishingAttempt(
                attempt_id=attempt_id,
                campaign_id=harvest_data.get("campaign_id", "unknown"),
                target=harvest_data.get("target", {}),
                attack_vector=harvest_data.get("attack_vector", "email"),
                status="credential_submitted" if harvest_data.get("credentials_submitted", False) else "failed",
                timestamp=datetime.now(),
                ip_address=harvest_data.get("ip_address", ""),
                user_agent=harvest_data.get("user_agent", ""),
                source_url=harvest_data.get("source_url"),
                credentials_attempted=harvest_data.get("credentials_submitted", False),
                outcome="success" if harvest_data.get("credentials_submitted", False) else "failure",
                detection_result=harvest_data.get("detection_result")
            )

            self.phishing_attempts.append(attempt)

            # Generate report
            report_id = f"report_{datetime.now().timestamp()}"
            report_data = {
                "report_id": report_id,
                "campaign_id": harvest_data.get("campaign_id"),
                "timestamp": datetime.now().isoformat(),
                "result": "success" if harvest_data.get("credentials_submitted", False) else "failure",
                "target": harvest_data.get("target", {}),
                "attack_vector": harvest_data.get("attack_vector", "email"),
                "user_agent": harvest_data.get("user_agent", ""),
                "ip_address": harvest_data.get("ip_address", "")
            }

            logger.info(f"Processed credential harvest attempt {attempt_id}")

            return {
                "attempt_id": attempt_id,
                "report_id": report_id,
                "status": "processed",
                "message": f"Credential harvest attempt processed: {attempt.attempt_id}"
            }

        @self.app.post("/security-training-modules")
        async def create_training_module(request: Request, training_data: Dict[str, Any]) -> Dict[str, str]:
            module_id = f"module_{datetime.now().timestamp()}"
            training_module = SecurityTrainingModule(
                module_id=module_id,
                title=training_data.get("title", "New Training Module"),
                description=training_data.get("description", ""),
                content=training_data.get("content", ""),
                interactive=training_data.get("interactive", False),
                difficulty=training_data.get("difficulty", "medium"),
                estimated_time=training_data.get("estimated_time", 60),
                prerequisites=training_data.get("prerequisites", []),
                learning_objectives=training_data.get("learning_objectives", []),
                completion_tracking=training_data.get("completion_tracking", True)
            )

            self.security_training_modules.append(training_module)

            logger.info(f"Created security training module {module_id}: {training_module.title}")

            return {
                "module_id": module_id,
                "status": "created",
                "message": f"Security training module created: {training_module.title}"
            }

        @self.app.get("/security-training-modules")
        async def list_training_modules(request: Request) -> Dict[str, Any]:
            return {
                "modules": [module.dict() for module in self.security_training_modules],
                "count": len(self.security_training_modules)
            }

        @self.app.get("/statistics")
        async def get_statistics(request: Request) -> Dict[str, Any]:
            campaigns = list(self.phishing_campaigns.values())
            attempts = self.phishing_attempts

            active_campaigns = len([c for c in campaigns if c.status == "active"])
            deception_frameworks = len(self.deception_frameworks)

            attempts_by_status = {}
            for attempt in attempts:
                attempts_by_status[attempt.status] = attempts_by_status.get(attempt.status, 0) + 1

            attempts_by_attack_vector = {}
            for attempt in attempts:
                attempts_by_attack_vector[attempt.attack_vector] = attempts_by_attack_vector.get(attempt.attack_vector, 0) + 1

            credential_submissions = len([a for a in attempts if a.credentials_attempted])

            return {
                "campaigns": {
                    "total": len(campaigns),
                    "active": active_campaigns,
                    "by_status": {
                        "draft": len([c for c in campaigns if c.status == "draft"]),
                        "active": active_campaigns,
                        "paused": len([c for c in campaigns if c.status == "paused"]),
                        "completed": len([c for c in campaigns if c.status == "completed"]),
                        "cancelled": len([c for c in campaigns if c.status == "cancelled"])
                    }
                },
                "attempts": {
                    "total": len(attempts),
                    "by_status": attempts_by_status,
                    "by_attack_vector": attempts_by_attack_vector,
                    "credential_submissions": credential_submissions,
                    "submission_rate": (credential_submissions / len(attempts) * 100) if attempts else 0
                },
                "deception_frameworks": {
                    "total": len(self.deception_frameworks),
                    "effectiveness_score": sum(f["effectiveness_score"] for f in self.deception_frameworks.values()) / len(self.deception_frameworks) if self.deception_frameworks else 0
                },
                "security_training": {
                    "total_modules": len(self.security_training_modules)
                },
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }

    async def _campaign_scheduler_loop(self) -> None:
        """Campaign scheduler loop"""
        while self.is_running:
            try:
                # Check for campaigns to start
                for campaign_id, campaign in list(self.phishing_campaigns.items()):
                    if campaign.status == "draft" and campaign.scheduled_start:
                        if campaign.scheduled_start <= datetime.now():
                            campaign.status = "active"
                            logger.info(f"Scheduled campaign {campaign_id} started automatically")

                # Check for campaigns to stop
                for campaign_id, campaign in list(self.phishing_campaigns.items()):
                    if campaign.status == "active" and campaign.scheduled_end:
                        if campaign.scheduled_end <= datetime.now():
                            campaign.status = "completed"
                            logger.info(f"Scheduled campaign {campaign_id} completed automatically")

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in campaign scheduler loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry

    async def _attempt_tracker_loop(self) -> None:
        """Attempt tracker loop"""
        while self.is_running:
            try:
                # Generate simulated attempts for active campaigns
                for campaign_id, campaign in list(self.phishing_campaigns.items()):
                    if campaign.status == "active":
                        # Simulate attempts for random targets
                        for target in campaign.targets[:5]:  # Limit to 5 attempts per run
                            attempt_data = {
                                "campaign_id": campaign_id,
                                "target": target,
                                "attack_vector": campaign.attack_vector,
                                "ip_address": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
                                "user_agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(90, 120)}.0.0.0 Safari/537.36",
                                "source_url": f"https://campaign.example.com/{campaign_id}/email",
                                "credentials_submitted": random.choice([True, False]),
                                "outcome": "success" if random.choice([True, False]) else "failure",
                                "detection_result": None
                            }

                            # Create attempt
                            await self.create_attempt(None, attempt_data)

                await asyncio.sleep(random.randint(30, 120))  # Random interval

            except Exception as e:
                logger.error(f"Error in attempt tracker loop: {e}")
                await asyncio.sleep(600)  # Wait 10 minutes before retry

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return {
            "status": "healthy" if self.is_running else "stopped",
            "campaigns": len(self.phishing_campaigns),
            "deception_frameworks": len(self.deception_frameworks),
            "attempts": len(self.phishing_attempts),
            "security_training_modules": len(self.security_training_modules),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }