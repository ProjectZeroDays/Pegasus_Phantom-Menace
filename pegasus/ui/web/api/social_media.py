"""pegasus ui web api social_media
"""# Social Media API Endpoints
# Pegasus Phantom Menace v2 - Social Media Intelligence API
#
# REST API endpoints for social media intelligence gathering and threat analysis.
#
# Part of Phase 15 implementation


from flask import Blueprint, jsonify, request
from pegasus.modules.social_media import SocialMediaAnalyzer
from pegasus.core.config import get_settings

# Initialize social media analyzer
social_media_analyzer = SocialMediaAnalyzer()

# Configure with API keys from environment (in production)
# For development, we'll use sample clients
social_media_analyzer.register_platform_client("twitter", None)  # Would use tweepy in production
social_media_analyzer.register_platform_client("linkedin", None)  # Would use linkedin-api in production
social_media_analyzer.register_platform_client("instagram", None)  # Would use instaloader in production
social_media_analyzer.register_platform_client("facebook", None)  # Would use facebook-sdk in production

social_media_bp = Blueprint("social_media")
@social_media_bp.get("/health")
def health_check():
    """Health check for social media API.""""
    return jsonify({"ok": True, "status": "healthy", "service": "social_media"})
@social_media_bp.get("/intelligence")
def get_intelligence():
    """Get threat intelligence from social media platforms.""""
    try:
        timeframe = request.args.get("hours", 24, type=int)
        report = social_media_analyzer.get_intel_report(timeframe)
        return jsonify({"ok": True, "data": report})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
@social_media_bp.get("/threats")
def get_threats():
    """Get current threat alerts.""""
    try:
        threshold = float(request.args.get("threshold", 0.3))
        alerts = social_media_analyzer.monitor_threat_activity(threshold)
        return jsonify({"ok": True, "data": alerts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
@social_media_bp.post("/analyze")
def analyze_content():
    """Analyze content for threat patterns.""""
    try:
        data = request.get_json() or {}
        content = data.get("content", "")
        platform = data.get("platform", "general")
        
        if not content:
            return jsonify({"ok": False, "error": "Content is required"}), 400
        
        scores = social_media_analyzer.analyze_content(content, platform)
        return jsonify({"ok": True, "data": scores})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
@social_media_bp.get("/platforms")
def get_platforms():
    """Get supported social media platforms.""""
    platforms = list(social_media_analyzer.platform_clients.keys())
    return jsonify({"ok": True, "data": platforms})
@social_media_bp.post("/register")
def register_platform():
    """Register a new social media platform client.""""
    try:
        data = request.get_json() or {}
        platform = data.get("platform", "")
        client = data.get("client")
        
        if not platform or not client:
            return jsonify({"ok": False, "error": "Platform and client are required"}), 400
        
        social_media_analyzer.register_platform_client(platform, client)
        return jsonify({"ok": True, "message": f"Platform {platform} registered successfully"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
@social_media_bp.get("/reports")
def get_reports():
    """Generate intelligence reports for different timeframes.""""
    try:
        timeframe = request.args.get("hours", 24, type=int)
        report = social_media_analyzer.get_intel_report(timeframe)
        return jsonify({"ok": True, "data": report})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
# Register the blueprint
__all__ = [social_media_bp]

# The social_media_bp provides comprehensive API endpoints for:
# - Health checking
# - Threat intelligence gathering
# - Content analysis and correlation
# - Alert monitoring
# - Report generation
# - Platform management
# - Intelligence retrieval
#
# All endpoints are REST APIs with JSON request/response format.
#
# Security features:
# - Input validation
# - Error handling
# - CORS support (inherited from main app)
# - Rate limiting (in production)
#
# Usage example:
#
# GET /api/social_media/intelligence?hours=48
# Returns intelligence report for last 48 hours
#
# POST /api/social_media/analyze
# {"content": "URGENT: Click here for access", "platform": "twitter"}
# Returns threat analysis scores
#
# GET /api/social_media/threats?threshold=0.5
# Returns high-priority threat alerts
#
# GET /api/social_media/platforms
# Returns list of supported platforms
#
# This API is part of Pegasus Phantom Menace v2's Phase  tensity intelligence gathering capabilities."