# Enterprise Social Engineering Module
# Advanced phishing campaigns, deception frameworks, and security training platform
# Features:
# - Phishing campaign management
# - Deception framework generation
# - Credential harvesting tracking
# - Security training modules
# - Campaign scheduling
# - Attempt simulation and tracking
# - Deception tactic libraries
# - Attack vector optimization

from .social_server import (
    SocialEngineeringServer,
    PhishingCampaign,
    DeceptionFramework,
    PhishingAttempt,
    SecurityTrainingModule,
)

__all__ = [
    "SocialEngineeringServer",
    "PhishingCampaign",
    "DeceptionFramework",
    "PhishingAttempt",
    "SecurityTrainingModule",
]