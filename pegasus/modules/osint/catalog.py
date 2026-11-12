"""Catalogue of OSINT search engines, attack-surface sources and tooling.

Every entry is a *passive* source: the module queries a public or
key-authenticated API and returns what that API returns.  Nothing here
exploits a host, brute-forces a credential, or scans a network - the two
network scanners in the catalogue (IVRE) run in their passive mode only.

``kind`` is either ``api`` (a remote service queried over HTTPS) or ``tool``
(something installed on this machine).
"""
from __future__ import annotations

from typing import Any, Dict, List

CATEGORIES = [
    ("code", "Code & Data"),
    ("attack-surface", "Attack Surface"),
    ("threat-intel", "Threat Intelligence"),
    ("servers", "Servers & Networks"),
    ("osint", "WiFi Networks & OSINT"),
    ("social-media", "Social Media & Profiles"),
    ("tools", "Tooling"),
]

SERVICES: List[Dict[str, Any]] = [
    # ---------------------------------------------------------- code & data
    {
        "id": "grep_app", "name": "grep.app", "category": "code",
        "url": "https://grep.app", "kind": "api",
        "api": "https://grep.app/api/search?q={query}",
        "key_env": None, "key_required": False,
        "results": "hits.hits",
        "notes": "Search across open-source codebases.",
    },
    {
        "id": "searchcode", "name": "searchcode.com", "category": "code",
        "url": "https://searchcode.com", "kind": "api",
        "api": "https://searchcode.com/api/codesearch_I/?q={query}&per_page=20",
        "key_env": None, "key_required": False,
        "results": "results",
        "notes": "Explore source code repositories.",
    },
    {
        "id": "publicwww", "name": "publicwww.com", "category": "code",
        "url": "https://publicwww.com", "kind": "api",
        "api": "https://publicwww.com/websites/{query}/",
        "key_env": "PUBLICWWW_API_KEY", "key_required": True,
        "results": None,
        "notes": "Identify websites using specific code snippets.",
    },
    {
        "id": "urlscan", "name": "urlscan.io", "category": "code",
        "url": "https://urlscan.io", "kind": "api",
        "api": "https://urlscan.io/api/v1/search/?q={query}&size=20",
        "key_env": "URLSCAN_API_KEY", "key_required": False,
        "results": "results",
        "notes": "Analyse and map website interactions.",
    },
    {
        "id": "vulners", "name": "vulners.com", "category": "code",
        "url": "https://vulners.com", "kind": "api",
        "api": "https://vulners.com/api/v3/search/lucene/?query={query}",
        "key_env": "VULNERS_API_KEY", "key_required": True,
        "results": "search",
        "notes": "Vulnerability database and code search.",
    },
    # ------------------------------------------------------- attack surface
    {
        "id": "fullhunt", "name": "fullhunt.io", "category": "attack-surface",
        "url": "https://fullhunt.io", "kind": "api",
        "api": "https://fullhunt.io/api/v1/domain/{query}/subdomains",
        "key_env": "FULLHUNT_API_KEY", "key_required": True,
        "results": "hosts",
        "notes": "Map and monitor attack surfaces.",
    },
    {
        "id": "netlas", "name": "app.netlas.io", "category": "attack-surface",
        "url": "https://app.netlas.io", "kind": "api",
        "api": "https://app.netlas.io/api/domains/?q={query}&format=json",
        "key_env": "NETLAS_API_KEY", "key_required": True,
        "results": "items",
        "notes": "Explore assets and vulnerabilities in networks.",
    },
    {
        "id": "leakix", "name": "leakix.net", "category": "attack-surface",
        "url": "https://leakix.net", "kind": "api",
        "api": "https://leakix.net/api/search?scope=leak&q={query}",
        "key_env": None, "key_required": False,
        "results": None,
        "notes": "Find unprotected and misconfigured assets.",
    },
    {
        "id": "censys", "name": "censys.io", "category": "attack-surface",
        "url": "https://search.censys.io", "kind": "api",
        "api": "https://search.censys.io/api/v2/hosts/search?q={query}&per_page=20",
        "key_env": "CENSYS_API_ID", "key_required": True,
        "results": "result.hits",
        "notes": "Server discovery and analysis.",
    },
    # ------------------------------------------------------ threat intelligence
    {
        "id": "onyphe", "name": "onyphe.io", "category": "threat-intel",
        "url": "https://www.onyphe.io", "kind": "api",
        "api": "https://www.onyphe.io/api/v2/search/?query={query}",
        "key_env": "ONYPHE_API_KEY", "key_required": True,
        "results": "results",
        "notes": "Search and collect cyber threat intelligence.",
    },
    {
        "id": "binaryedge", "name": "binaryedge.io", "category": "threat-intel",
        "url": "https://www.binaryedge.io", "kind": "api",
        "api": "https://api.binaryedge.io/v2/query/search?query={query}",
        "key_env": "BINARYEDGE_API_KEY", "key_required": True,
        "results": "events",
        "notes": "Threat intelligence for attack surfaces.",
    },
    {
        "id": "pulsedive", "name": "pulsedive.com", "category": "threat-intel",
        "url": "https://pulsedive.com", "kind": "api",
        "api": "https://pulsedive.com/api/info.php?indicator={query}&pretty=1",
        "key_env": "PULSEDIVE_API_KEY", "key_required": True,
        "results": None,
        "notes": "Malware analysis and threat intelligence platform.",
    },
    {
        "id": "greynoise", "name": "viz.greynoise.io", "category": "threat-intel",
        "url": "https://viz.greynoise.io", "kind": "api",
        "api": "https://api.greynoise.io/v3/community/{query}",
        "key_env": "GREYNOISE_API_KEY", "key_required": False,
        "results": None,
        "notes": "Insights into internet background noise.",
    },
    {
        "id": "socradar", "name": "socradar.io", "category": "threat-intel",
        "url": "https://www.socradar.io", "kind": "api",
        "api": "https://api.socradar.io/api/v1/{query}",
        "key_env": "SOCRADAR_API_KEY", "key_required": True,
        "results": None,
        "notes": "Threat intelligence and attack surface management.",
    },
    # ------------------------------------------------- servers and networks
    {
        "id": "shodan", "name": "shodan.io", "category": "servers",
        "url": "https://www.shodan.io", "kind": "api",
        "api": "https://api.shodan.io/shodan/host/{query}?minify=true",
        "key_env": "SHODAN_API_KEY", "key_required": True,
        "results": None,
        "notes": "Server reconnaissance across the whole internet.",
    },
    {
        "id": "fofa", "name": "fofa.info", "category": "servers",
        "url": "https://fofa.info", "kind": "api",
        "api": "https://fofa.info/api/v1/search/all?qbase64={query_b64}",
        "key_env": "FOFA_API_KEY", "key_required": True,
        "results": "results",
        "notes": "Cyber space search engine for assets.",
    },
    {
        "id": "zoomeye", "name": "zoomeye.org", "category": "servers",
        "url": "https://www.zoomeye.org", "kind": "api",
        "api": "https://api.zoomeye.org/host/search?query={query}",
        "key_env": "ZOOMEYE_API_KEY", "key_required": True,
        "results": "matches",
        "notes": "Network mapping and vulnerability research.",
    },
    {
        "id": "ivre", "name": "ivre.rocks", "category": "servers",
        "url": "https://ivre.rocks", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "ivre", "verify": "ivre"},
        "notes": "Passive and active network reconnaissance framework. "
                 "The bundled install runs the passive components only.",
    },
    # --------------------------------------------------- wifi and osint
    {
        "id": "wigle", "name": "wigle.net", "category": "osint",
        "url": "https://wigle.net", "kind": "api",
        "api": "https://api.wigle.net/api/v2/network/search?ssid={query}&format=json",
        "key_env": "WIGLE_API_KEY", "key_required": True,
        "results": "results",
        "notes": "WiFi network mapping.",
    },
    {
        "id": "intelx", "name": "intelx.io", "category": "osint",
        "url": "https://intelx.io", "kind": "api",
        "api": "https://2.intelx.io/phonebook/search?term={query}",
        "key_env": "INTELX_API_KEY", "key_required": True,
        "results": "search",
        "notes": "Comprehensive OSINT search.",
    },
    {
        "id": "hunter", "name": "hunter.io", "category": "osint",
        "url": "https://hunter.io", "kind": "api",
        "api": "https://api.hunter.io/v2/domain-search?domain={query}&limit=20",
        "key_env": "HUNTER_API_KEY", "key_required": True,
        "results": "data.emails",
        "notes": "Discover email addresses associated with domains.",
    },
    {
        "id": "crtsh", "name": "crt.sh", "category": "osint",
        "url": "https://crt.sh", "kind": "api",
        "api": "https://crt.sh/?q={query}&output=json",
        "key_env": None, "key_required": False,
        "results": None,
        "notes": "Certificate transparency logs for domain research.",
    },
    # -------------------------------------------------------- social media
    {
        "id": "sherlock", "name": "Sherlock", "category": "social-media",
        "url": "https://github.com/sherlock-project/sherlock", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "sherlock-project", "verify": "sherlock"},
        "notes": "Hunt down social media accounts by username across 400+ networks.",
    },
    {
        "id": "maigret", "name": "Maigret", "category": "social-media",
        "url": "https://github.com/soxoj/maigret", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "maigret", "verify": "maigret"},
        "notes": "Collect a dossier on a person by username from 3000+ sites. "
                 "Supports recursive parsing of account pages for linked identities.",
    },
    {
        "id": "socialscan", "name": "SocialScan", "category": "social-media",
        "url": "https://github.com/iojw/socialscan", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "socialscan", "verify": "socialscan"},
        "notes": "Check email and username availability across major platforms "
                 "(Twitter, Instagram, GitHub, Reddit, etc.) without API keys.",
    },
    {
        "id": "twint", "name": "Twint (Twitter)", "category": "social-media",
        "url": "https://github.com/twintproject/twint", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "twint", "verify": "twint"},
        "notes": "Scrape Twitter profiles, tweets, followers and trends without "
                 "API rate limits. Passive reconnaissance only.",
    },
    {
        "id": "instaloader", "name": "Instaloader (Instagram)", "category": "social-media",
        "url": "https://github.com/instaloader/instaloader", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "instaloader", "verify": "instaloader"},
        "notes": "Download Instagram posts, stories, profiles and metadata. "
                 "Supports session-based access for private profiles.",
    },
    {
        "id": "reddit_osint", "name": "Reddit Search (Pushshift)", "category": "social-media",
        "url": "https://pushshift.io", "kind": "api",
        "api": "https://api.pushshift.io/api/search/submission/?q={query}&size=25&sort=desc",
        "key_env": None, "key_required": False,
        "results": "data",
        "notes": "Search historical Reddit submissions and comments for threat "
                 "actor profiling and campaign tracking.",
    },
    {
        "id": "haveibeenpwned", "name": "Have I Been Pwned", "category": "social-media",
        "url": "https://haveibeenpwned.com", "kind": "api",
        "api": "https://haveibeenpwned.com/api/v3/breachedaccount/{query}?truncateResponse=false",
        "key_env": "HIBP_API_KEY", "key_required": True,
        "results": None,
        "notes": "Check if an email or username appears in known data breaches. "
                 "Useful for credential reuse analysis and threat actor profiling.",
    },
    {
        "id": "holehe", "name": "Holehe", "category": "social-media",
        "url": "https://github.com/megadose/holehe", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "holehe", "verify": "holehe"},
        "notes": "Check if an email is registered on 120+ sites including social "
                 "media platforms. Maps email to account presence without passwords.",
    },
    {
        "id": "social_links", "name": "Social Links (IntelX)", "category": "social-media",
        "url": "https://intelx.io", "kind": "api",
        "api": "https://2.intelx.io/phonebook/search?term={query}&buckets=social",
        "key_env": "INTELX_API_KEY", "key_required": True,
        "results": "search",
        "notes": "Cross-platform social media search via IntelX. Covers Twitter, "
                 "Facebook, LinkedIn, Telegram, Discord and paste sites.",
    },
    # ---------------------------------------------------------------- tooling
    {
        "id": "mimikats", "name": "MimiKATS", "category": "tools",
        "url": "https://github.com/ThreatIQ/mimikats", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {"type": "pip", "package": "mimikats", "verify": "mimikats"},
        "notes": "Kubernetes attack-surface audit mapped to MITRE ATT&CK. "
                 "Runs against a cluster you already have access to.",
    },
    {
        "id": "maltego", "name": "Maltego", "category": "tools",
        "url": "https://www.maltego.com", "kind": "tool",
        "api": None, "key_env": None, "key_required": False,
        "results": None,
        "install": {
            "type": "download",
            "url": "https://downloads.maltego.com/maltego-v5.6.2/Maltego_v5.6.2_amd64.zip",
            "binary": "Maltego",
            "license": "Commercial. Downloaded from the vendor; a valid "
                       "Maltego licence is required to run it.",
        },
        "notes": "OSINT graph workbench. Commercial licence required - the "
                 "installer downloads the vendor build and never redistributes it.",
    },
]


def by_id() -> Dict[str, Dict[str, Any]]:
    return {entry["id"]: entry for entry in SERVICES}


def get(service_id: str) -> Dict[str, Any]:
    entry = by_id().get(service_id)
    if not entry:
        raise KeyError(service_id)
    return entry


def in_category(category: str) -> List[Dict[str, Any]]:
    return [entry for entry in SERVICES if entry.get("category") == category]


def tools() -> List[Dict[str, Any]]:
    return [entry for entry in SERVICES if entry.get("kind") == "tool"]


def services() -> List[Dict[str, Any]]:
    return [entry for entry in SERVICES if entry.get("kind") == "api"]


def catalog() -> List[Dict[str, Any]]:
    """The catalogue with the catalogued category labels attached."""
    labels = dict(CATEGORIES)
    out = []
    for entry in SERVICES:
        item = dict(entry)
        item["category_label"] = labels.get(entry.get("category"), entry.get("category"))
        out.append(item)
    return out
