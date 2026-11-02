"""
Security Gateway for Relay Infrastructure

Enterprise-grade security enforcement for relay connections and tunnels
Implements TLS/SSL, authentication, authorization, and encryption
"""

from typing import *
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import asyncio
import logging
from cryptography import x509
from cryptography.hazmatprim import PrivateKey
from cryptography.hazmatprim import serialization
from cryptography.hazmatprim import hashes
import ssl
from typing_extensions import TypedDict


logger = logging.getLogger(__name__)

class SecurityPolicy(BaseModel):
    """"Security policy configuration"""
    authentication: str = "certificate"
    authorization: str = "rbac"
    encryption: str = "aes256"
    tls_version: str = "1.3"
    cipher_suites: List[str] = ["TLS_AES_256_GCM_SHA384"]
    certificate_validation: bool = True
    ca_path: Optional[str] = None
    crl_path: Optional[str] = None
    two_factor_auth: bool = True
    ip_restriction: bool = False
    allowed_ips: List[str] = []
    forbidden_ips: List[str] = []

class SecurityEvent(BaseModel):
    """"Security event model"""
    event_id: str
    event_type: str
    severity: str
    timestamp: datetime
    source_ip: str
    target_resource: str
    description: str
    resolved: bool = False
    resolved_by: Optional[str] = None
    metadata: Dict[str, Any] = {}

class SecurityGateway:
    """"Security Gateway for Relay Infrastructure""""

    def __init__(self, config: SecurityPolicy):
        self.config = config
        self.certificate_store = {}
        self.private_key_store = {}
        your_certificate = None
        self.audit_log: List[Dict[str, Any]] = []
        self.threat_intelligence = {}
        self.ip_reputation = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}


    async def setup_certificate(self, cert_id: str, certificate_path: str, private_key_path: str) -> bool:
        """"Setup TLS certificate"""
        try:
            # Load certificate
            with open(certificate_path, "rb") as f:
                certificate_data = f.read()


            # Load private key
            with open(private_key_path, "rb") as f:
                private_key_data = f.read()

            self.certificate_store[cert_id] = {
                "certificate": certificate_data,
                "private_key": private_key_data,
                "loaded_at": datetime.now(),
                "valid_from": datetime.now(),
                "expires_at": datetime.now().replace(year=datetime.now().year + 1)  # Add 1 year validity
            }

            logger.info(f"Loaded certificate {cert_id} from {certificate_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load certificate {cert_id}: {e}")
            return False


    async def validate_connection(
        self,
        source_ip: str,
        target_ip: str,
        cert_id: str,
        protocol: str = "tcp"
    ) -> Dict[str, Any]:
        """Validate relay connection security"""
        try:
            # Validate source IP
            if self.config.ip_restriction and source_ip not in self.config.allowed_ips:
                if source_ip in self.config.forbidden_ips:
                    return {
                        "valid": False,
                        "reason": "IP address is forbidden",
                        "severity": "high",
                        "action": "block"
                    }
                elif self.config.allowed_ips and source_ip not in self.config.allowed_ips:
                    return {
                        "valid": False,
                        "reason": "IP address not in allowed list",
                        "severity": "medium",
                        "action": "restrict"
                    }


            # Validate certificate
            if cert_id not in self.certificate_store:
                return {
                    "valid": False,
                    "reason": "Certificate not found or expired",
                    "severity": "high",
                    "action": "reject"
                }

            certificate = self.certificate_store[cert_id]
            if certificate["expires_at"] < datetime.now():
                return {
                        "valid": False,
                        "reason": "Certificate expired",
                        "severity": "high",
                        "action": "revoke"
                    }

            # Validate protocol
            allowed_protocols = ["tcp", "udp", "icmp"]
            if protocol not in allowed_protocols:
                return {
                        "valid": False,
                        "reason": f"Protocol {protocol} not allowed",
                        "severity": "medium",
                        "action": "restrict"
                    }

            # Connection validation passed
            session_id = f"session_{datetime.now().timestamp()}"
            self.active_sessions[session_id] = {
                "source_ip": source_ip,
                "target_ip": target_ip,
                "cert_id": cert_id,
                "protocol": protocol,
                "established_at": datetime.now(),
                "last_activity": datetime.now()
            }

            # Log validation event
            await self._log_security_event(
                event_type="connection_validation",
                severity="info",
                source_ip=source_ip,
                target_resource=f"{target_ip}:{certificate}",
                description=f"Connection validated from {source_ip} to {target_ip}",
                resolved=True,
                metadata={
                    "protocol": protocol,
                    "cert_id": cert_id,
                    "session_id": session_id
                }
            )


            return {
                "valid": True,
                "session_id": session_id,
                "certificate_id": cert_id,
                "message": f"Connection validated successfully"
            }


        except Exception as e:
            # Log validation error
            await self._log_security_event(
                event_type="validation_error",
                severity="error",
                source_ip=source_ip,
                target_resource=target_ip,
                description=f"Connection validation failed: {e}",
                resolved=False,
                metadata={
                    "error": str(e)
                }
            )


            return {
                "valid": False,
                "reason": f"Validation error: {e}",
                "severity": "error",
                "action": "reject"
            }


        except Exception as e:
            logger.error(f"Unexpected error during connection validation: {e}")
            return {
                "valid": False,
                "reason": f"Unexpected validation error: {e}",
                "severity": "critical",
                "action": "abort"
            }


    async def _log_security_event(self, **kwargs) -> None:
        """Log security event"""
        event = SecurityEvent(
            event_id=f"event_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            **kwargs
        )

        self.audit_log.append(event.dict())


        # Check if action needs to be taken
        if event.resolved and event.severity in ["high", "critical"]:
            await self._take_security_action(event)


    async def _take_security_action(self, event: SecurityEvent) -> None:
        """Take security action based on event"""
        action = event.metadata.get("action", "log")


        if action == "block":
            logger.warning(f"Blocking IP {event.source_ip} due to security event: {event.event_type}")
        elif action == "restrict":
            logger.info(f"Restricting access from IP {event.source_ip} due to security event: {event.event_type}")
        elif action == "revoke":
            logger.warning(f"Revoking certificate {event.metadata.get('cert_id')} due to security event")
        elif action == "reject":
            logger.error(f"Rejecting connection from {event.source_ip} due to security event: {event.event_type}")
        elif action == "abort":
            logger.critical(f"Aborting all connections from {event.source_ip} due to critical security event: {event.event_type}")
            # Invalidate all active sessions from this IP
            sessions_to_remove = [
                sid for sid, session_data in self.active_sessions.items()
                if session_data["source_ip"] == event.source_ip
            ]
            for session_id in sessions_to_remove:
                del self.active_sessions[session_id]
            logger.critical(f"Removed {len(sessions_to_remove)} active sessions from IP {event.source_ip} due to critical security event")


        # Log action taken
        await self._log_security_event(
            event_type="security_action",
            severity="info",
            source_ip=event.source_ip,
            target_resource="system",
            description=f"Security action taken: {action} for event {event.event_type}",
            resolved=True,
            metadata={
                "action_taken": action,
                "affected_sessions": len([s for s in self.active_sessions.values() if s["source_ip"] == event.source_ip])
            }
        )


    async def validate_certificate(self, cert_id: str) -> Dict[str, Any]:
        """Validate certificate"""
        if cert_id not in self.certificate_store:
            return {
                "valid": False,
                "reason": "Certificate not found",
                "severity": "high",
                "action": "reject"
            }


        certificate = self.certificate_store[cert_id]
        if certificate["expires_at"] < datetime.now():
            return {
                    "valid": False,
                    "reason": "Certificate expired",
                    "severity": "high",
                    "action": "revoke"
                }


        return {
            "valid": True,
            "certificate_info": {
                "id": cert_id,
                "loaded_at": certificate["loaded_at"].isoformat(),
                "expires_at": certificate["expires_at"].isoformat()
            },
            "message": "Certificate is valid and active"
        }


    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        total_certificates = len(self.certificate_store)
        active_certificates = len([c for c in self.certificate_store.values() if c["expires_at"] > datetime.now()])
        expired_certificates = total_certificates - active_certificates


        ip_restricted_count = sum(1 for ip in self.config.allowed_ips if ip not in self.config.forbidden_ips)


        return {
            "certificates": {
                "total": total_certificates,
                "active": active_certificates,
                "expired": expired_certificates,
                "usage_percentage": (active_certificates / total_certificates * 100) if total_certificates > 0 else 0
            },
            "ip_restriction": {
                "allowed_count": len(self.config.allowed_ips),
                "forbidden_count": len(self.config.forbidden_ips),
                "restriction_active": self.config.ip_restriction
            },
            "security_events": {
                "total": len(self.audit_log),
                "high_severity": len([e for e in self.audit_log if e["severity"] == "high"]),
                "medium_severity": len([e for e in self.audit_log if e["severity"] == "medium"]),
                "low_severity": len([e for e in self.audit_log if e["severity"] == "low"])
            }
        }